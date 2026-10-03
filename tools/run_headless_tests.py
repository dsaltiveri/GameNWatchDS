#!/usr/bin/env python3
"""Official GameNWatchDS acceptance tests using BlocksDS Testing."""

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile

from PIL import Image, ImageChops

from game_catalog import gnw_path, load_catalog


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MSYS2 = Path("C:/msys64")
DEFAULT_COMPAT = (DEFAULT_MSYS2 / "home" /
                  os.environ.get("USERNAME", "dsalt") /
                  "blocksds_testing_windows")
DEFAULT_BLOBS = (DEFAULT_MSYS2 / "home" /
                 os.environ.get("USERNAME", "dsalt") /
                 "blocksds-test-blobs")
DEFAULT_BIOS = Path("C:/melonDS/Bios")
DEFAULT_VISUAL_BASELINE = ROOT / "tools" / "visual_baselines.json"


def load_test_modules(compat_path):
    if os.name == "nt":
        if not compat_path.is_dir():
            raise RuntimeError(
                f"Missing Windows BlocksDS Testing adapter: {compat_path}")
        sys.path.insert(0, str(compat_path))
    try:
        import blocksds_testing as blocksds  # noqa: PLC0415
        from libretro import JoypadState, UnformattedLogDriver  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            f"BlocksDS Testing or a dependency is unavailable: {exc}") from exc
    return blocksds, JoypadState, UnformattedLogDriver


def crc16(data):
    value = 0xFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = ((value >> 1) ^ 0xA001) if value & 1 else value >> 1
    return value


def make_ds_test_rom(source, destination):
    """Create an NTR-header copy without altering the production ROM."""
    data = bytearray(source.read_bytes())
    if len(data) < 0x160:
        raise RuntimeError("ROM is too small to contain an NDS header")
    data[0x12] &= ~0x02
    struct.pack_into("<H", data, 0x15E, crc16(data[:0x15E]))
    destination.write_bytes(data)
    return destination


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hardlink(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError as exc:
        raise RuntimeError(
            f"Could not create temporary hard link {destination} -> {source}: "
            f"{exc}") from exc


def resolve_blobs(blobs, bios_dir, destination):
    """Expose canonical BlocksDS names as temporary links to local files."""
    core_name = "melondsds_libretro.dll" if os.name == "nt" else \
                "melondsds_libretro.so"
    candidates = {
        core_name: (blobs / core_name,),
        "bios7.bin": (blobs / "bios7.bin", bios_dir / "bios7.bin",
                      bios_dir / "biosnds7.bin"),
        "bios9.bin": (blobs / "bios9.bin", bios_dir / "bios9.bin",
                      bios_dir / "biosnds9.bin"),
        "bios7i.bin": (blobs / "bios7i.bin", bios_dir / "bios7i.bin",
                       bios_dir / "biosdsi7.bin"),
        "bios9i.bin": (blobs / "bios9i.bin", bios_dir / "bios9i.bin",
                       bios_dir / "biosdsi9.bin"),
        "dsfirmware.bin": (blobs / "dsfirmware.bin",
                           bios_dir / "dsfirmware.bin",
                           bios_dir / "dsifirmware.bin"),
        "nand.bin": (blobs / "nand.bin", bios_dir / "nand.bin",
                     bios_dir / "dsinand.bin"),
    }
    resolved = {}
    missing = []
    for expected, choices in candidates.items():
        source = next((item.resolve() for item in choices if item.is_file()), None)
        if source is None:
            missing.append(f"{expected} (tried: {', '.join(map(str, choices))})")
            continue
        target = destination / expected
        hardlink(source, target)
        resolved[expected] = str(source)
    if missing:
        raise RuntimeError("Missing melonDS core/BIOS resource(s):\n" +
                           "\n".join(missing))
    return resolved


def add_frames(timeline, frames, state=None):
    timeline.extend([state] * frames)


def press(timeline, joypad, frames=4, release=12, **buttons):
    add_frames(timeline, frames, joypad(**buttons))
    add_frames(timeline, release)


def make_timeline(catalog, selected, joypad):
    timeline = []
    cases = []
    add_frames(timeline, 360)

    if len(selected) == 1:
        target = catalog.index(selected[0])
        for _ in range(target):
            press(timeline, joypad, down=True)
        add_frames(timeline, 30)

    for index, game in enumerate(selected):
        add_frames(timeline, 30)
        checkpoints = {"selected": len(timeline)}
        press(timeline, joypad, a=True, release=20)
        add_frames(timeline, 180)

        # GAME A must be held long enough for slow-starting titles.
        press(timeline, joypad, frames=30, release=90, start=True)
        checkpoints["playing-a"] = len(timeline)

        # Common, deterministic controls: GAME B, TIME, ALARM, directions and
        # the four face buttons (including useful direction/action combos).
        press(timeline, joypad, frames=30, release=30, select=True)
        press(timeline, joypad, frames=20, release=30, l=True)
        press(timeline, joypad, frames=20, release=30, l=True, r=True)
        press(timeline, joypad, frames=16, release=24, right=True, a=True)
        press(timeline, joypad, frames=16, release=24, left=True, y=True)
        press(timeline, joypad, frames=16, release=24, up=True, x=True)
        press(timeline, joypad, frames=16, release=24, down=True, b=True)
        add_frames(timeline, 300)
        checkpoints["playing-b"] = len(timeline)

        press(timeline, joypad, r=True, release=120)
        checkpoints["returned"] = len(timeline)
        cases.append((game, checkpoints))

        if index + 1 < len(selected):
            press(timeline, joypad, down=True)

    return timeline, cases


def screenshot(session):
    frame = session.video.screenshot()
    return Image.frombytes("RGBA", (256, 384), frame.data.obj).convert("RGB")


def valid_game_image(image):
    colors = image.getcolors(256 * 384)
    color_count = 256 * 384 if colors is None else len(colors)
    nonblack = (256 * 384 if colors is None else
                sum(count for count, color in colors
                    if color != (0, 0, 0)))
    return color_count >= 8 and nonblack >= 1000


def difference_ratio(first, second):
    difference = ImageChops.difference(first, second)
    colors = difference.getcolors(256 * 384)
    if colors is None:
        return 1.0
    changed = sum(count for count, color in colors if color != (0, 0, 0))
    return changed / (256 * 384)


def image_fingerprint(image):
    """Exact RGB fingerprint for deterministic visual regression checks."""
    digest = hashlib.sha256()
    digest.update(image.mode.encode("ascii"))
    digest.update(struct.pack("<II", *image.size))
    digest.update(image.tobytes())
    return digest.hexdigest()


def validate_case(game, images, samples):
    errors = []
    if not valid_game_image(images["playing-a"]):
        errors.append("invalid gameplay image")
    if difference_ratio(images["selected"], images["playing-a"]) == 0:
        errors.append("gameplay is identical to menu selection")
    if difference_ratio(images["playing-a"], images["playing-b"]) == 0:
        errors.append("gameplay image is frozen")

    peak = max((abs(int(sample)) for sample in samples), default=0)
    nonzero = sum(int(sample) != 0 for sample in samples)
    if nonzero == 0:
        errors.append("audio remained silent")

    return_delta = difference_ratio(images["selected"], images["returned"])
    returned_to_menu = return_delta <= 0.03 and \
        difference_ratio(images["playing-b"], images["returned"]) > 0
    if not returned_to_menu:
        errors.append("did not return to the menu")

    return {
        "game": game.slug,
        "name": game.name,
        "passed": not errors,
        "errors": errors,
        "audio_samples": len(samples),
        "audio_nonzero": nonzero,
        "audio_peak": peak,
        "visual_changed": difference_ratio(
            images["playing-a"], images["playing-b"]) > 0,
        "returned_to_menu": returned_to_menu,
        "menu_return_difference": round(return_delta, 6),
        "visual_fingerprints": {
            name: image_fingerprint(image) for name, image in images.items()
        },
    }


def load_visual_baseline(path):
    if not path.is_file():
        return {"schema": 1, "games": {}}
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid visual baseline {path}: {exc}") from exc
    if baseline.get("schema") != 1 or not isinstance(baseline.get("games"), dict):
        raise RuntimeError(f"Invalid visual baseline schema: {path}")
    return baseline


def apply_visual_baseline(results, baseline):
    checked = 0
    for result in results:
        expected = baseline["games"].get(result["game"])
        if not expected:
            continue
        checked += 1
        actual = result["visual_fingerprints"]
        mismatches = [name for name, digest in expected.items()
                      if actual.get(name) != digest]
        if mismatches:
            result["errors"].append(
                "visual baseline mismatch: " + ", ".join(mismatches))
            result["passed"] = False
        result["visual_baseline_checked"] = True
    return checked


def update_visual_baseline(path, baseline, results):
    for result in results:
        fingerprints = result["visual_fingerprints"]
        baseline["games"][result["game"]] = {
            name: fingerprints[name] for name in ("playing-a", "playing-b")
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def run_session(blocksds, joypad, log_driver_type, rom, dldi_root, output,
                catalog, selected, keep_screenshots):
    timeline, cases = make_timeline(catalog, selected, joypad)
    logs = log_driver_type()
    results = []

    with blocksds.session_start(
            str(rom), timeline, logs, {"melonds_console_mode": "ds"},
            user_dldi_root=str(dldi_root)) as session:
        current = 0
        for index, (game, checkpoints) in enumerate(cases, 1):
            print(f"[{index}/{len(cases)}] {game.slug} - {game.name}",
                  flush=True)
            images = {}
            audio_start = len(session.audio.buffer)
            for name, target in checkpoints.items():
                blocksds.session_run_frames(session, target - current)
                current = target
                images[name] = screenshot(session)
            samples = tuple(session.audio.buffer[audio_start:])
            result = validate_case(game, images, samples)
            result["frames"] = checkpoints["returned"] - checkpoints["selected"]
            results.append(result)
            if keep_screenshots:
                for name, image in images.items():
                    image.save(output / f"{game.slug}-{name}.png")

    blocksds.assert_no_errors_in_logs(logs)
    messages = [str(record.message).lower() for record in logs.records]
    forbidden = ("data abort", "failed to load")
    found = sorted({needle for needle in forbidden
                    if any(needle in message for message in messages)})
    if found:
        raise RuntimeError("melonDS log contains: " + ", ".join(found))

    del session
    gc.collect()
    return results, len(timeline)


def parse_args(catalog):
    parser = argparse.ArgumentParser(
        description="Test GameNWatchDS with BlocksDS Testing/melonDS DS.")
    parser.add_argument("--game", choices=("all",) + tuple(
        game.slug for game in catalog), default="all")
    parser.add_argument("--rom", type=Path, default=ROOT / "GameNWatchDS.nds")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "build" / "melonds-headless")
    parser.add_argument("--blobs", type=Path,
                        default=Path(os.environ.get(
                            "BLOCKSDS_TESTING_BLOBS", DEFAULT_BLOBS)))
    parser.add_argument("--bios-dir", type=Path, default=DEFAULT_BIOS)
    parser.add_argument("--blocksds-testing", type=Path,
                        default=Path(os.environ.get(
                            "GNWDS_BLOCKSDS_TESTING", DEFAULT_COMPAT)))
    parser.add_argument("--no-screenshots", action="store_true")
    parser.add_argument("--visual-baseline", type=Path,
                        default=DEFAULT_VISUAL_BASELINE,
                        help="JSON fingerprints to verify (default: %(default)s)")
    parser.add_argument("--update-visual-baseline", action="store_true",
                        help="replace baseline entries for the selected game(s)")
    return parser.parse_args()


def main():
    catalog = load_catalog(ROOT)
    args = parse_args(catalog)
    rom = args.rom.resolve()
    if not rom.is_file():
        raise RuntimeError(f"Missing ROM: {rom} (run make first)")
    all_missing = [str(gnw_path(ROOT, game)) for game in catalog
                   if not gnw_path(ROOT, game).is_file()]
    if all_missing:
        raise RuntimeError(
            "Missing .gnw file(s); the menu must expose the entire catalog:\n" +
            "\n".join(all_missing))

    selected = catalog if args.game == "all" else tuple(
        game for game in catalog if game.slug == args.game)
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    original_hash = file_hash(rom)
    blocksds, joypad, log_driver = load_test_modules(
        args.blocksds_testing.resolve())

    results = []
    total_frames = 0
    suite_error = None
    baseline_path = args.visual_baseline.resolve()
    baseline = load_visual_baseline(baseline_path)
    visual_baselines_checked = 0
    try:
        with tempfile.TemporaryDirectory(prefix="gnwds-headless-",
                                         dir=output) as temporary:
            work = Path(temporary)
            resolved = work / "blobs"
            blob_sources = resolve_blobs(args.blobs.resolve(),
                                           args.bios_dir.resolve(), resolved)
            os.environ["BLOCKSDS_TESTING_BLOBS"] = str(resolved.resolve())
            test_rom = make_ds_test_rom(rom, work / "GameNWatchDS-NTR.nds")
            results, total_frames = run_session(
                blocksds, joypad, log_driver, test_rom,
                ROOT / "shrinker" / "output", output, catalog, selected,
                not args.no_screenshots)
            if args.update_visual_baseline:
                update_visual_baseline(baseline_path, baseline, results)
            visual_baselines_checked = apply_visual_baseline(results, baseline)
    except (AssertionError, OSError, RuntimeError, ValueError) as exc:
        suite_error = str(exc)
        blob_sources = {}

    unchanged = file_hash(rom) == original_hash
    if not unchanged:
        suite_error = "Production ROM changed during headless testing"
    summary = {
        "suite": "BlocksDS Testing / melonDS DS",
        "mode": "DS",
        "catalog_entries": len(catalog),
        "tested": len(results),
        "passed": sum(item["passed"] for item in results),
        "failed": sum(not item["passed"] for item in results),
        "total_frames": total_frames,
        "visual_baseline": str(baseline_path),
        "visual_baselines_checked": visual_baselines_checked,
        "production_rom_unchanged": unchanged,
        "temporary_blob_sources": blob_sources,
        "suite_error": suite_error,
        "games": results,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items()
                      if key not in ("games", "temporary_blob_sources")},
                     indent=2))
    if suite_error:
        raise RuntimeError(suite_error)
    if summary["failed"]:
        failed = ", ".join(item["game"] for item in results
                           if not item["passed"])
        raise RuntimeError(f'{summary["failed"]} game(s) failed: {failed}')


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)


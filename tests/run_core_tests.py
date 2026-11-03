#!/usr/bin/env python3
"""Compile and run the deterministic host core harness."""

import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile


# Reuse the canonical catalog and conversion helpers from tools.
sys.path.append(str(Path(__file__).resolve().parents[1] / "tools"))

from game_catalog import gnw_path, load_catalog


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GCC = Path("C:/msys64/ucrt64/bin/gcc.exe")


def parse_args(catalog):
    parser = argparse.ArgumentParser(
        description="Run host diagnostics against GameNWatchDS .gnw files.")
    parser.add_argument("--game", choices=("all",) + tuple(
        game.slug for game in catalog), default="all")
    parser.add_argument("--cc", type=Path,
                        help="Host GCC executable (auto-detected by default)")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "build" / "core-tests")
    return parser.parse_args()


def find_gcc(requested):
    if requested:
        if requested.is_file():
            return requested.resolve()
        raise RuntimeError(f"Requested host GCC does not exist: {requested}")
    candidates = []
    if os.environ.get("GNWDS_HOST_CC"):
        candidates.append(Path(os.environ["GNWDS_HOST_CC"]))
    candidates.append(DEFAULT_GCC)
    discovered = shutil.which("gcc")
    if discovered:
        candidates.append(Path(discovered))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError(
        "Host GCC not found; install MSYS2 UCRT64 GCC or pass --cc PATH")


def compile_harness(cc, executable):
    cpu = ROOT / "arm9" / "source" / "cpus"
    system = ROOT / "arm9" / "source" / "gw_sys"
    sources = [
        ROOT / "tests" / "harness" / "harness.c",
        cpu / "sm500core.c", cpu / "sm500op.c", cpu / "sm5acore.c",
        cpu / "sm510base.c", cpu / "sm510core.c", cpu / "sm510op.c",
        cpu / "sm511core.c", system / "gw_system.c",
        system / "gw_graphic.c", system / "gw_romloader.c",
    ]
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise RuntimeError("Missing harness source: " + ", ".join(missing))
    executable.parent.mkdir(parents=True, exist_ok=True)
    command = [str(cc), "-std=c11", "-O2", "-Wall", "-Wextra",
               "-DHARNESS_DEBUG", *(str(path) for path in sources),
               "-I" + str(cpu), "-I" + str(system),
               "-I" + str(ROOT / "arm9" / "source"),
               "-o", str(executable)]
    environment = os.environ.copy()
    environment["PATH"] = str(cc.parent) + os.pathsep + environment.get("PATH", "")
    result = subprocess.run(command, text=True, capture_output=True,
                            env=environment)
    if result.returncode:
        detail = (result.stdout + result.stderr).strip()
        raise RuntimeError(
            f"Harness compilation failed (exit {result.returncode}):\n" +
            (detail or "compiler produced no diagnostics"))


def compiler_environment(compiler_dir):
    environment = os.environ.copy()
    environment["PATH"] = str(compiler_dir) + os.pathsep + environment.get(
        "PATH", "")
    return environment


def run_one(executable, game, rom, compiler_dir):
    result = subprocess.run([str(executable), str(rom)], text=True,
                            capture_output=True,
                            env=compiler_environment(compiler_dir))
    output = (result.stdout + result.stderr).strip()
    if output:
        print(output)
    return {
        "game": game.slug,
        "name": game.name,
        "rom": str(rom),
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "result": next((line for line in output.splitlines()
                        if line.startswith("RESULT ")), ""),
    }


def run_loader_negative_tests(executable, compiler_dir, source_rom, out):
    """Confirm malformed package metadata is rejected by the real loader."""
    original = source_rom.read_bytes()
    mutations = {}

    mutations["truncated_header"] = original[:64]

    data = bytearray(original)
    data[0:8] = b"BADCPU__"
    mutations["unsupported_cpu"] = data

    data = bytearray(original)
    struct.pack_into("<I", data, 40, 1020)  # segments_offset_size
    mutations["short_geometry_array"] = data

    data = bytearray(original)
    struct.pack_into("<I", data, 96, 32)  # only eight keyboard rows
    mutations["short_keyboard"] = data

    data = bytearray(original)
    struct.pack_into("<I", data, 80, 128)  # melody_size
    mutations["invalid_melody_size"] = data

    data = bytearray(original)
    struct.pack_into("<I", data, 24, 98304)  # only one backdrop
    mutations["invalid_backdrop_size"] = data

    data = bytearray(original)
    segments_offset = struct.unpack_from("<I", data, 36)[0]
    struct.pack_into("<I", data, 36, segments_offset + 2)
    mutations["misaligned_block"] = data

    data = bytearray(original)
    struct.pack_into("<I", data, 84, len(data) - 2048)
    mutations["block_out_of_range"] = data

    data = bytearray(original)
    segments_offset = struct.unpack_from("<I", data, 36)[0]
    struct.pack_into("<I", data, 44, segments_offset)
    mutations["overlapping_blocks"] = data

    data = bytearray(original)
    offsets_at = struct.unpack_from("<I", data, 36)[0]
    heights_at = struct.unpack_from("<I", data, 60)[0]
    widths_at = struct.unpack_from("<I", data, 68)[0]
    pixel_nibbles = struct.unpack_from("<I", data, 32)[0] * 2
    active = next(index for index in range(256)
                  if struct.unpack_from("<H", data, widths_at + index * 2)[0]
                  and struct.unpack_from(
                      "<H", data, heights_at + index * 2)[0])
    struct.pack_into("<I", data, offsets_at + active * 4, pixel_nibbles)
    mutations["segment_pixels_out_of_range"] = data

    results = []
    with tempfile.TemporaryDirectory(prefix="invalid-gnw-", dir=out) as temp:
        temp_dir = Path(temp)
        for name, content in mutations.items():
            path = temp_dir / f"{name}.gnw"
            path.write_bytes(content)
            result = subprocess.run(
                [str(executable), str(path)], text=True, capture_output=True,
                env=compiler_environment(compiler_dir))
            output = result.stdout + result.stderr
            rejected = (result.returncode != 0 and
                        "real .gnw loader rejected" in output)
            results.append({"case": name, "rejected": rejected,
                            "returncode": result.returncode})
            print(f"[loader] {name}: " +
                  ("rejected" if rejected else "FAIL"), flush=True)
    return results


def main():
    catalog = load_catalog(ROOT)
    args = parse_args(catalog)
    selected = catalog if args.game == "all" else tuple(
        game for game in catalog if game.slug == args.game)

    missing = [str(gnw_path(ROOT, game)) for game in selected
               if not gnw_path(ROOT, game).is_file()]
    if missing:
        raise RuntimeError(
            "Missing .gnw file(s); run GNWBuilder.exe first:\n" +
            "\n".join(missing))

    out = args.out.resolve()
    executable = out / ("core_harness.exe" if os.name == "nt"
                         else "core_harness")
    cc = find_gcc(args.cc)
    print(f"Compiling harness with {cc}", flush=True)
    compile_harness(cc, executable)

    loader_tests = run_loader_negative_tests(
        executable, cc.parent, gnw_path(ROOT, catalog[0]), out)

    results = []
    for index, game in enumerate(selected, 1):
        print(f"[{index}/{len(selected)}] {game.slug} - {game.name}", flush=True)
        results.append(run_one(executable, game, gnw_path(ROOT, game),
                               cc.parent))

    summary = {
        "suite": "GameNWatchDS core harness",
        "catalog_entries": len(catalog),
        "tested": len(results),
        "passed": sum(item["passed"] for item in results),
        "failed": sum(not item["passed"] for item in results),
        "loader_negative_tests": loader_tests,
        "games": results,
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items()
                      if key != "games"}, indent=2))
    loader_failures = sum(not item["rejected"] for item in loader_tests)
    if loader_failures:
        raise RuntimeError(
            f"{loader_failures} malformed .gnw loader test(s) failed")
    if summary["failed"]:
        raise RuntimeError(f'{summary["failed"]} core test(s) failed')


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)

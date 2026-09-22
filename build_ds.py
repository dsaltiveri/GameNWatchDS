#!/usr/bin/env python3
"""Build, synchronize and optionally launch GameNWatchDS for local testing.

The Makefiles remain the canonical build interface. This helper adds the
Windows development workflow around them: incremental/rebuild builds,
generation of missing .gnw files, synchronization to a melonDS virtual SD,
and optional emulator launch.
"""

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
GNW_DIR = HERE / "shrinker" / "output" / "gnw"
NDS_PATH = HERE / "GameNWatchDS.nds"
DEFAULT_MAKE = "C:/msys64/usr/bin/make.exe"
DEFAULT_MELONDS = "C:/melonDS/melonDS.exe"
DEFAULT_SD_DIR = "C:/melonDS/SD"

TOOLCHAIN_DEFAULTS = {
    "BLOCKSDS": "C:/msys64/opt/blocksds/core",
    "BLOCKSDSEXT": "C:/msys64/opt/blocksds/external",
    "WONDERFUL_TOOLCHAIN": "C:/msys64/opt/wonderful",
}


def build_env():
    """Returns an environment suitable for the BlocksDS Makefiles."""
    env = dict(os.environ)
    for name, default in TOOLCHAIN_DEFAULTS.items():
        env.setdefault(name, default)

    extra_path = [
        "C:/msys64/usr/bin",
        str(Path(env["WONDERFUL_TOOLCHAIN"]) / "toolchain" /
            "gcc-arm-none-eabi" / "bin"),
        str(Path(env["WONDERFUL_TOOLCHAIN"]) / "bin"),
    ]
    env["PATH"] = os.pathsep.join(extra_path + [env.get("PATH", "")])
    return env


def catalog_gnw_files():
    """Reads the .gnw filenames from the per-game C descriptors."""
    games_dir = HERE / "arm9" / "source" / "games"
    pattern = re.compile(r'\.rom_path\s*=\s*"/gnw/([^"/]+\.gnw)"')
    names = []
    for source in sorted(games_dir.glob("game_*.c")):
        matches = pattern.findall(source.read_text(encoding="utf-8"))
        if len(matches) != 1:
            raise RuntimeError(
                "%s: expected exactly one /gnw/*.gnw rom_path, found %d"
                % (source, len(matches)))
        names.append(matches[0])

    if not names:
        raise RuntimeError("no game descriptors found in %s" % games_dir)
    duplicates = sorted(name for name in set(names) if names.count(name) > 1)
    if duplicates:
        raise RuntimeError("duplicate rom_path entries: %s" % ", ".join(duplicates))
    return tuple(names)


def run(args, env):
    """Runs a command with live output and returns its process exit code."""
    print("RUN:", subprocess.list2cmdline([str(arg) for arg in args]))
    try:
        completed = subprocess.run(
            [str(arg) for arg in args], cwd=HERE, env=env, check=False)
    except OSError as exc:
        print("ERROR: cannot run %s: %s" % (args[0], exc), file=sys.stderr)
        return 127
    if completed.returncode:
        print("ERROR: command failed with exit code %d" % completed.returncode,
              file=sys.stderr)
    return completed.returncode


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_if_changed(src, dst):
    """Copies src to dst when needed. Returns True if a copy was made."""
    if dst.is_file() and sha256(src) == sha256(dst):
        return False
    shutil.copy2(src, dst)
    return True


def ensure_gnw(game_files, env):
    """Regenerates all .gnw files when one or more catalog entries are missing."""
    missing = [name for name in game_files if not (GNW_DIR / name).is_file()]
    if not missing:
        return True

    print("GNW missing: %s" % ", ".join(missing))
    script = HERE / "shrinker" / "shrink_gnw.py"
    if run([sys.executable, script], env) != 0:
        return False

    still_missing = [name for name in game_files
                     if not (GNW_DIR / name).is_file()]
    if still_missing:
        print("ERROR: .gnw still missing: %s" % ", ".join(still_missing),
              file=sys.stderr)
        return False
    return True


def sync_sd(game_files, sd_dir):
    """Synchronizes the .gnw files and the compiled ROM to a virtual SD."""
    dst_dir = sd_dir / "gnw"

    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        print("SYNC SD:", sd_dir)

        for name in game_files:
            src = GNW_DIR / name
            if not src.is_file():
                print("ERROR: missing source file: %s" % src, file=sys.stderr)
                return False
            copied = copy_if_changed(src, dst_dir / name)
            print("  %-24s %s" % (name, "copied" if copied else "ok (same)"))

        if not NDS_PATH.is_file():
            print("ERROR: compiled ROM not found: %s" % NDS_PATH,
                  file=sys.stderr)
            return False
        dst_nds = sd_dir / NDS_PATH.name
        copied = copy_if_changed(NDS_PATH, dst_nds)
        print("  %-24s %s" %
              (NDS_PATH.name, "copied" if copied else "ok (same)"))
    except OSError as exc:
        print("ERROR: SD synchronization failed: %s" % exc, file=sys.stderr)
        return False
    return True


def launch_emulator(melonds):
    if not melonds.is_file():
        print("ERROR: melonDS not found: %s" % melonds, file=sys.stderr)
        return False
    if not NDS_PATH.is_file():
        print("ERROR: compiled ROM not found: %s" % NDS_PATH, file=sys.stderr)
        return False

    print("LAUNCH melonDS:", NDS_PATH)
    try:
        subprocess.Popen([str(melonds), str(NDS_PATH)], cwd=melonds.parent)
    except OSError as exc:
        print("ERROR: melonDS launch failed: %s" % exc, file=sys.stderr)
        return False
    return True


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build GameNWatchDS and prepare a melonDS virtual SD.")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--clean", action="store_true",
                        help="clean build artifacts and exit")
    action.add_argument("--rebuild", action="store_true",
                        help="clean before building")
    action.add_argument("--sync-only", action="store_true",
                        help="skip the build, synchronize existing outputs and exit")
    parser.add_argument("--no-sync", action="store_true",
                        help="do not generate/synchronize SD assets")
    parser.add_argument("--no-launch", action="store_true",
                        help="do not launch melonDS after a successful build")
    parser.add_argument("--make", default=os.environ.get("GNWDS_MAKE", DEFAULT_MAKE),
                        help="make executable (env: GNWDS_MAKE)")
    parser.add_argument("--melonds",
                        default=os.environ.get("GNWDS_MELONDS", DEFAULT_MELONDS),
                        help="melonDS executable (env: GNWDS_MELONDS)")
    parser.add_argument("--sd-dir",
                        default=os.environ.get("GNWDS_SD_DIR", DEFAULT_SD_DIR),
                        help="melonDS virtual SD root (env: GNWDS_SD_DIR)")

    raw = list(sys.argv[1:] if argv is None else argv)
    if raw == ["clean"]:  # Backward compatibility with the old script.
        raw = ["--clean"]
    args = parser.parse_args(raw)
    if args.sync_only and args.no_sync:
        parser.error("--sync-only cannot be combined with --no-sync")
    return args


def main(argv=None):
    args = parse_args(argv)
    env = build_env()

    if args.clean:
        return run([args.make, "clean"], env)

    try:
        game_files = catalog_gnw_files()
    except (OSError, UnicodeError, RuntimeError) as exc:
        print("ERROR: cannot read game catalog: %s" % exc, file=sys.stderr)
        return 1

    if args.rebuild:
        rc = run([args.make, "clean"], env)
        if rc != 0:
            return rc

    if not args.sync_only:
        rc = run([args.make, "COMPDB=1"], env)
        if rc != 0:
            return rc
        if not NDS_PATH.is_file():
            print("ERROR: build succeeded but did not create %s" % NDS_PATH,
                  file=sys.stderr)
            return 1
        print("NDS: %s (%d bytes)" % (NDS_PATH, NDS_PATH.stat().st_size))

    if not args.no_sync:
        if not ensure_gnw(game_files, env):
            return 1
        if not sync_sd(game_files, Path(args.sd_dir).expanduser()):
            return 1

    if not args.no_launch and not args.sync_only:
        if not launch_emulator(Path(args.melonds).expanduser()):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

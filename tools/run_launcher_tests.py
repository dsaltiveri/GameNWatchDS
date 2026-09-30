#!/usr/bin/env python3
"""Compile and run host tests for TWiLight/libnds argv path handling."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from game_catalog import gnw_path, load_catalog
from run_core_tests import compiler_environment, find_gcc


ROOT = Path(__file__).resolve().parents[1]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test direct .gnw launch argument and device resolution.")
    parser.add_argument("--cc", type=Path,
                        help="Host GCC executable (auto-detected by default)")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "build" / "launcher-tests")
    return parser.parse_args()


def compile_harness(cc, executable):
    sources = [ROOT / "tools" / "_harness" / "test_launcher.c",
               ROOT / "arm9" / "source" / "launcher.c"]
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise RuntimeError("Missing launcher harness source: " +
                           ", ".join(missing))
    command = [str(cc), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
               "-DLAUNCHER_HOST_TEST", *(str(path) for path in sources),
               "-I" + str(ROOT / "arm9" / "source"), "-o", str(executable)]
    result = subprocess.run(
        command, text=True, capture_output=True,
        env=compiler_environment(cc.parent))
    if result.returncode:
        detail = (result.stdout + result.stderr).strip()
        raise RuntimeError(
            f"Launcher harness compilation failed (exit {result.returncode}):\n" +
            (detail or "compiler produced no diagnostics"))


def main():
    args = parse_args()
    catalog = load_catalog(ROOT)
    source = gnw_path(ROOT, catalog[0])
    if not source.is_file():
        raise RuntimeError(f"Missing .gnw file: {source}")

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    executable = out / ("launcher_harness.exe" if os.name == "nt" else
                        "launcher_harness")
    cc = find_gcc(args.cc)
    compile_harness(cc, executable)

    with tempfile.TemporaryDirectory(prefix="virtual-sd-", dir=out) as temp:
        virtual_root = Path(temp)
        sd_dir = virtual_root / "sd" / "roms" / "gnw"
        fat_dir = virtual_root / "fat" / "roms" / "gnw"
        sd_dir.mkdir(parents=True)
        fat_dir.mkdir(parents=True)
        shutil.copy2(source, sd_dir / "direct.GNW")
        shutil.copy2(source, fat_dir / "fallback.gnw")
        shutil.copy2(source, fat_dir / "renamed")
        (fat_dir / "truncated.gnw").write_bytes(source.read_bytes()[:8])

        result = subprocess.run(
            [str(executable), str(virtual_root), str(source.resolve())],
            text=True, capture_output=True,
            env=compiler_environment(cc.parent))
        output = (result.stdout + result.stderr).strip()
        if output:
            print(output)

    summary = {
        "suite": "GameNWatchDS direct-launch host harness",
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "result": next((line for line in output.splitlines()
                        if line.startswith("RESULT ")), ""),
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        raise RuntimeError("Direct-launch host tests failed")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)

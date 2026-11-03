#!/usr/bin/env python3
"""Run the default host validation suites from any working directory."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SUITES = [['run_catalog_io_tests.py'], ['run_regression_tests.py'], ['-m', 'unittest', 'discover', '-s', 'GNWBuilder/tests']]


def command_for(suite):
    if suite[0] == "@powershell":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            raise RuntimeError("PowerShell is required for the ROM access suite")
        return [shell, "-NoProfile", "-File", str(ROOT / "tests" / suite[1])]
    if suite[0] == "@make":
        make = shutil.which("make") or ("C:/msys64/usr/bin/make.exe" if os.name == "nt" else "make")
        return [make, *suite[1:], "PYTHON=" + sys.executable.replace("\\", "/")]
    if suite[0] == "-m":
        return [sys.executable, *suite]
    return [sys.executable, str(ROOT / "tests" / suite[0]), *suite[1:]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List suites without running them")
    args = parser.parse_args()
    if args.list:
        for suite in SUITES:
            print(" ".join(suite))
        return 0
    env = os.environ.copy()
    if os.name == "nt":
        env["PATH"] = "C:/msys64/ucrt64/bin;C:/msys64/usr/bin;" + env.get("PATH", "")
    failures = []
    for suite in SUITES:
        print("Running " + " ".join(suite), flush=True)
        try:
            result = subprocess.run(command_for(suite), cwd=ROOT, env=env, check=False)
            if result.returncode:
                failures.append(suite)
        except (OSError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            failures.append(suite)
    print(f"Host validation: {len(SUITES) - len(failures)}/{len(SUITES)} suites passed")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())

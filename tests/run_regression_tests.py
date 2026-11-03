#!/usr/bin/env python3
"""Run ROM-free renderer and audio regressions against the production C code."""
import argparse
from pathlib import Path
import struct
import subprocess
import tempfile


# Reuse the canonical catalog and conversion helpers from tools.
import sys
sys.path.append(str(Path(__file__).resolve().parents[1] / "tools"))

from run_core_tests import compiler_environment, find_gcc
from run_launcher_tests import compile_harness as compile_launcher

ROOT = Path(__file__).resolve().parents[1]


def synthetic_package():
    """A valid package with a silent LBL loop; no commercial game data."""
    data = bytearray(100)
    blocks = {}
    for name, content in (
        ("pixels", b"\x00\x00\x00\x00"),
        ("offsets", bytes(1024)), ("xs", bytes(512)),
        ("ys", bytes(512)), ("heights", bytes(512)),
        ("widths", bytes(512)), ("program", bytes([0x5f]) * 4096),
        ("keyboard", bytes(40)), ("background", bytes(196608)),
    ):
        blocks[name] = (len(data), len(content))
        data.extend(content)
    header = [0, *blocks["background"], *blocks["pixels"],
              *blocks["offsets"], *blocks["xs"], *blocks["ys"],
              *blocks["heights"], *blocks["widths"], 0, 0,
              *blocks["program"], *blocks["keyboard"]]
    data[:100] = struct.pack("<8s8s21I", b"SM510___", b"test____", *header)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", type=Path)
    parser.add_argument("--sanitize", action="store_true",
                        help="Enable address and undefined-behavior sanitizers")
    args = parser.parse_args()
    cc = find_gcc(args.cc)
    cpu = ROOT / "arm9/source/cpus"
    system = ROOT / "arm9/source/gw_sys"
    sources = [ROOT / "tests/harness/test_regressions.c",
               *(p for p in sorted(cpu.glob("*.c")) if p.name != "sm511core.c"),
               *(system / name for name in
                 ("gw_system.c", "gw_graphic.c", "gw_romloader.c"))]
    with tempfile.TemporaryDirectory(prefix="gnw-regressions-") as directory:
        temp = Path(directory)
        executable = temp / "regressions"
        command = [str(cc), "-std=c11", "-O2", "-g", "-Wall", "-Wextra",
                   "-I" + str(ROOT / "tests/harness/nds-stub"),
                   "-I" + str(cpu), "-I" + str(system),
                   *(str(p) for p in sources), "-o", str(executable)]
        if args.sanitize:
            command[1:1] = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        environment = compiler_environment(cc.parent)
        subprocess.run(command, check=True, env=environment)
        package = temp / "synthetic.gnw"
        package.write_bytes(synthetic_package())
        no_melody = temp / "missing-melody.gnw"
        invalid = synthetic_package()
        invalid[:8] = b"SM511___"
        no_melody.write_bytes(invalid)
        subprocess.run([str(executable), str(package), str(no_melody)],
                       check=True, env=environment)
        launcher = temp / "launcher"
        compile_launcher(cc, launcher)
        for device, name in (("sd", "direct.GNW"), ("fat", "fallback.gnw"),
                             ("fat", "renamed"), ("fat", "truncated.gnw")):
            path = temp / device / "roms/gnw" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(package.read_bytes()[:8] if name == "truncated.gnw"
                             else package.read_bytes())
        subprocess.run([str(launcher), str(temp), str(package)],
                       check=True, env=environment)


if __name__ == "__main__":
    main()

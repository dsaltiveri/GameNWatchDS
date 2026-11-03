#!/usr/bin/env python3
"""ROM-free tests for header identity, expanding catalogs and file errors."""
import argparse
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile


# Reuse the canonical catalog and conversion helpers from tools.
import sys
sys.path.append(str(Path(__file__).resolve().parents[1] / "tools"))

from game_catalog import load_catalog
from run_core_tests import compiler_environment, find_gcc

ROOT = Path(__file__).resolve().parents[1]


def synthetic_package():
    data = bytearray(100)
    blocks = {}
    for name, content in (
        ("pixels", bytes(4)), ("offsets", bytes(1024)),
        ("xs", bytes(512)), ("ys", bytes(512)),
        ("heights", bytes(512)), ("widths", bytes(512)),
        ("program", bytes(4096)), ("keyboard", bytes(40)),
        ("background", bytes(196608)),
    ):
        blocks[name] = (len(data), len(content))
        data.extend(content)
    data[:100] = struct.pack(
        "<8s8s21I", b"SM5A____", b"w_ball__", 0,
        *blocks["background"], *blocks["pixels"], *blocks["offsets"],
        *blocks["xs"], *blocks["ys"], *blocks["heights"], *blocks["widths"],
        0, 0, *blocks["program"], *blocks["keyboard"])
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", type=Path)
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    cc = find_gcc(args.cc)
    source = ROOT / "arm9/source"
    stub = ROOT / "tests/harness/io-stub"
    catalog = load_catalog(ROOT)
    with tempfile.TemporaryDirectory(prefix="gnw-catalog-io-") as directory:
        temp = Path(directory)

        def compile_test(executable, harness, src, extra):
            command = [str(cc), "-std=c11", "-O2", "-g", "-Wall", "-Wextra",
                       "-Werror", "-DLAUNCHER_HOST_TEST", "-I" + str(stub), "-I" + str(src),
                       "-I" + str(source), "-I" + str(source / "cpus"),
                       "-I" + str(source / "gw_sys"),
                       str(ROOT / "tests/harness" / harness),
                       str(src / "games.c"),
                       *(str(p) for p in sorted((src / "games").glob("game_*.c"))),
                       *(str(p) for p in extra), "-o", str(executable)]
            if args.sanitize:
                command[1:1] = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
            subprocess.run(command, check=True, env=compiler_environment(cc.parent))

        executable = temp / "identity-io"
        compile_test(executable, "test_catalog_io.c", source,
                     [source / "launcher.c"])
        misleading = temp / "Fire.gnw"
        misleading.write_bytes(synthetic_package())
        valid = temp / "valid.gnw"
        valid.write_bytes(synthetic_package())
        subprocess.run([str(executable), str(misleading), str(valid)], check=True)

        # Compile the real menu with an expanded registry, without editing the repo.
        expanded_root = temp / "expanded"
        expanded = expanded_root / "arm9/source"
        expanded.mkdir(parents=True)
        for name in ("games.c", "games.h", "game_catalog.h", "menu.c", "menu.h"):
            shutil.copy2(source / name, expanded / name)
        shutil.copytree(source / "games", expanded / "games")
        registry = (expanded / "game_catalog.h").read_text()
        extra_names = [f"fixture{i}" for i in range(max(0, 70 - len(catalog)))]
        for i, name in enumerate(extra_names):
            (expanded / "games" / f"game_{name}.c").write_text(
                '#include "games.h"\n'
                f'const game_desc_t game_{name} = {{.name="Fixture {i}", '
                f'.rom_path="/gnw/Fixture {i}.gnw", .cpu="SM5A_", '
                f'.rom_sig="fix{i:05d}"}};\n')
        marker = registry.index("\n\n#endif")
        registry = (registry[:marker] +
                    "".join(" \\\n    X(" + name + ")" for name in extra_names) +
                    registry[marker:])
        (expanded / "game_catalog.h").write_text(registry)
        assert len(load_catalog(expanded_root)) == len(catalog) + len(extra_names)
        executable = temp / "menu-catalog"
        compile_test(executable, "test_menu_catalog.c", expanded, [source / "launcher.c"])
        packages = temp / "packages"
        packages.mkdir()
        menu_valid = temp / "menu-valid.gnw"
        menu_valid.write_bytes(synthetic_package())
        subprocess.run([str(executable), str(packages), str(menu_valid)], check=True)
        print(f"PASS: Python catalog expands from {len(catalog)} to "
              f"{len(catalog) + len(extra_names)} entries")


if __name__ == "__main__":
    main()

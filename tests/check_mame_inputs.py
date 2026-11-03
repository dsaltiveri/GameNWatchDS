# -*- coding: utf-8 -*-
"""Checks that the kb table of each .gnw (and GNWBuilder engine) is pure MAME.

Compares each slot of the keyboard table against the INPUT_PORTS of
MAME hh_sm510.cpp:

  - SM510/511/512: slot kb[i]  <-> IN.i   (S output bit i -> port IN.i)
  - SM5A/SM500:    slot kb[i]  <-> IN.(i-1)  (MAME piezo_input_w: input_w(R>>1))

Resolves PORT_INCLUDE( microvs_shared ) (boxing, dkhockey, dkong3) and the
dkcirc ports (shared with gnw_mmousep).

Rows with IPT_JOYSTICKLEFT_*/JOYSTICKRIGHT_* (abstract buttons of the
"specials": mario, bjack, flagman, judge, manhole, fireatk, lion,
manholeg, mmouse) are not compared: their GW label is decided by the
front-end game_*.c.

Usage:
    python tests/check_mame_inputs.py
    python tests/check_mame_inputs.py --engine
    python tests/check_mame_inputs.py --mame-source C:/src/mame/src/mame/handheld/hh_sm510.cpp

The MAME source can also be set with GNWDS_MAME_SOURCE.
"""
import argparse
from pathlib import Path
import re
import struct
import os
import sys

ROOT = Path(__file__).resolve().parents[1]

# Reuse the canonical catalog and conversion helpers from tools.
sys.path.append(str(Path(__file__).resolve().parents[1] / "tools"))

GNW = ROOT / "gnw"
ENGINE = ROOT / "GNWBuilder" / "gnw_builder_engine.py"
MAME_RELATIVE = Path("src/mame/handheld/hh_sm510.cpp")


def parse_block(t, name):
    """Returns {port_name: [(bit, ipt, port_name_txt)]} or None."""
    m = re.search(
        r"INPUT_PORTS_START\s*\(\s*%s\s*\)(.*?)INPUT_PORTS_END"
        % re.escape(name), t, re.S)
    if not m:
        return None
    rows = {}
    cur = None
    for line in m.group(1).splitlines():
        line = line.strip()
        ms = re.match(r'PORT_START\(\s*"([^"]+)"\s*\)', line)
        if ms:
            cur = ms.group(1)
            rows[cur] = []
            continue
        mb = re.match(
            r"PORT_BIT\(\s*(0x[0-9A-Fa-f]+)\s*,\s*IP_ACTIVE_HIGH\s*,\s*"
            r"([A-Z0-9_]+)\s*\)(.*)", line)
        if mb and cur is not None:
            nm = re.search(r'PORT_NAME\(\s*"([^"]*)"', mb.group(3))
            rows[cur].append(
                (int(mb.group(1), 16), mb.group(2),
                 nm.group(1) if nm else ""))
    return rows


def find_mame_source(requested=None):
    """Resolve an explicit path, the environment, or common local clones."""
    if requested is not None:
        candidates = (requested,)
    elif os.environ.get("GNWDS_MAME_SOURCE"):
        candidates = (Path(os.environ["GNWDS_MAME_SOURCE"]),)
    else:
        candidates = (
            ROOT / "tests" / "fixtures" / "mame" / "hh_sm510.cpp",
            ROOT.parent / "mame" / MAME_RELATIVE,
            Path("C:/mame") / MAME_RELATIVE,
        )
    for candidate in candidates:
        candidate = candidate.expanduser()
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "MAME hh_sm510.cpp not found; pass --mame-source PATH or set "
        "GNWDS_MAME_SOURCE (tried: %s)" %
        ", ".join(str(path) for path in candidates))


def load_mame(source):
    t = source.read_text(encoding="utf-8", errors="ignore")

    include_src = {}
    for m in re.finditer(
            r"INPUT_PORTS_START\s*\(\s*(\w+)\s*\)(.*?)INPUT_PORTS_END",
            t, re.S):
        inc = re.search(r"PORT_INCLUDE\(\s*(\w+)\s*\)", m.group(2))
        if inc:
            include_src[m.group(1)] = inc.group(1)

    blocks = {}
    for m in re.finditer(
            r"INPUT_PORTS_START\s*\(\s*(\w+)\s*\)(.*?)INPUT_PORTS_END",
            t, re.S):
        name = m.group(1)
        rows = parse_block(t, name)
        if rows is None:
            continue
        if name in include_src:  # merge the PORT_INCLUDE
            src = include_src[name]
            if src in blocks:
                rows = dict(blocks[src], **rows)
        blocks[name] = rows
    if "gnw_ball" not in blocks:
        raise ValueError(
            "%s does not look like MAME handheld/hh_sm510.cpp" % source)
    return blocks


BITK = {0x01: 0, 0x02: 1, 0x04: 2, 0x08: 3}
DIRMAP = {
    "IPT_JOYSTICK_UP": 0x02,
    "IPT_JOYSTICK_DOWN": 0x08,
    "IPT_JOYSTICK_LEFT": 0x01,
    "IPT_JOYSTICK_RIGHT": 0x04,
}
SPECIAL = ("IPT_JOYSTICKLEFT_UP", "IPT_JOYSTICKLEFT_DOWN",
           "IPT_JOYSTICKRIGHT_UP", "IPT_JOYSTICKRIGHT_DOWN")


def expected_row(entries):
    """kb value (u32) that MAME requires for a row, or None if it has
    abstract (special) IPTs that depend on the front-end."""
    b = [0, 0, 0, 0]
    for bit, ipt, nm in entries:
        k = BITK.get(bit)
        if k is None:
            continue
        if ipt in DIRMAP:
            b[k] = DIRMAP[ipt]
        elif ipt in SPECIAL:
            return None
        elif ipt == "IPT_BUTTON1":
            b[k] = 0x10
        elif ipt == "IPT_BUTTON2":
            b[k] = 0x20
        elif nm.lower() == "time":
            b[k] = 0x40
        elif ipt == "IPT_START1":
            b[k] = 0x80
        elif ipt == "IPT_START2":
            b[k] = 0x20
        elif nm.lower() == "alarm":
            b[k] = 0xA0
    return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)


def check(kb, blocks, gname, cpu):
    """Returns a list of (slot, mame_row, expected, actual) or None if the
    game has no INPUT_PORTS in MAME."""
    mame_name = "gnw_" + gname
    if mame_name not in blocks:
        return None  # no MAME ports (not verifiable)
    if mame_name == "gnw_dkcirc":   # dkcirc shares ports with mmousep
        mame_name = "gnw_mmousep"
    rows = blocks[mame_name]
    sm5a = cpu.startswith("SM5A") or cpu.startswith("SM500")
    bad = []
    for i, val in enumerate(kb):
        if val == 0:
            continue
        row = i if not sm5a else i - 1   # shift SM5A (IN.x <-> R bit x+1)
        rn = "IN.%d" % row
        if rn not in rows:
            continue
        exp = expected_row(rows[rn])
        if exp is None:
            continue  # abstract row (the front-end decides the label)
        if exp != val:
            bad.append((i, rn, exp, val))
    return bad


def parse_engine_kb():
    """Return the keyboard tables declared in GNWBuilder's engine."""
    src = ENGINE.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r'^\s{4}"([a-z0-9]+)":\s*\{', src, re.M):
        g = m.group(1)
        i = m.end()
        depth = 1
        j = i
        while depth > 0 and j < len(src):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
            j += 1
        blk = src[i:j]
        km = re.search(r'"kb"\s*:\s*\[([^\]]*)\]', blk)
        if km:
            out[g] = [int(x, 16) if "x" in x else int(x)
                      for x in km.group(1).split(",") if x.strip()]
    return out


def gnw_slugs():
    """Map generated .gnw filenames (menu titles) to catalog slugs."""
    from game_catalog import load_catalog
    return {Path(game.rom_path).name.casefold(): game.slug
            for game in load_catalog(ROOT)}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare GameNWatchDS keyboard tables with MAME.")
    parser.add_argument("--engine", action="store_true",
                        help="check GNWBuilder's engine instead of generated .gnw files")
    parser.add_argument("--mame-source", type=Path,
                        help="path to MAME hh_sm510.cpp "
                             "(env: GNWDS_MAME_SOURCE)")
    parser.add_argument("--gnw-dir", type=Path, default=GNW,
                        help="generated .gnw directory")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        mame_source = find_mame_source(args.mame_source)
    except FileNotFoundError as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2
    try:
        blocks = load_mame(mame_source)
    except (OSError, UnicodeError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2
    print("MAME:", mame_source)
    if args.engine:
        print("== GNWBuilder engine vs MAME ==")
        sm5a_games = {"chef", "fire", "ball", "vermin", "helmet",
                      "octopus", "pchute", "popeye", "egg", "flagman",
                      "judge", "manholeg", "lion", "fires", "mmouse"}
        nbad = 0
        for g, kb in parse_engine_kb().items():
            if g == "fire":
                continue  # FR-27: specific K filter (is_sm5a_keyboard in gw_system.c)
            cpu = "SM5A___" if g in sm5a_games else "SM511__"
            bad = check(kb, blocks, g, cpu)
            if bad:
                nbad += 1
                for slot, rn, exp, act in bad:
                    print("  !! %-9s kb[%d]=0x%08X  MAME %s=0x%08X"
                          % (g, slot, act, rn, exp))
        print("mismatches:", nbad)
        return 1 if nbad else 0

    print("== .gnw files in gnw/ vs MAME ==")
    gnw_dir = args.gnw_dir.resolve()
    if not gnw_dir.is_dir():
        print("ERROR: .gnw directory not found: %s" % gnw_dir,
              file=sys.stderr)
        return 2
    nbad = 0
    slugs = gnw_slugs()
    for path in sorted(gnw_dir.iterdir()):
        if path.suffix.lower() != ".gnw":
            continue
        g = slugs.get(path.name.casefold())
        if g is None:
            print("     %-9s unknown package name (not in catalog)" % path.stem)
            continue
        gw = path.read_bytes()
        off = struct.unpack_from("<I", gw, 92)[0]
        sz = struct.unpack_from("<I", gw, 96)[0]
        kb = [struct.unpack_from("<I", gw, off + 4 * i)[0]
              for i in range(sz // 4)]
        cpu, _sig = game_cpu_sig(gw)
        if g == "fire":
            continue  # FR-27: specific K filter (is_sm5a_keyboard in gw_system.c)
        bad = check(kb, blocks, g, cpu)
        if bad is None:
            continue
        if bad:
            nbad += 1
            for slot, rn, exp, act in bad:
                print("  !! %-9s kb[%d]=0x%08X  MAME %s=0x%08X"
                      % (g, slot, act, rn, exp))
        else:
            print("     %-9s OK" % g)
    print("mismatches:", nbad)
    return 1 if nbad else 0


def game_cpu_sig(rom):
    """cpu_name and rom_signature of a .gnw."""
    return rom[0:8].decode("latin1").strip("\x00 "), rom[8:16].decode("latin1")


if __name__ == "__main__":
    sys.exit(main())

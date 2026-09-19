# -*- coding: utf-8 -*-
"""Checks that the kb table of each .gnw (and shrink_gnw.py) is pure MAME.

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
    python tools/_check_mame_kb.py            # vs the .gnw files in gnw/
    python tools/_check_mame_kb.py --py       # vs the kb declared in shrink_gnw.py
"""
import re
import struct
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GNW = os.path.join(ROOT, "shrinker", "output", "gnw")
PY = os.path.join(ROOT, "shrinker", "shrink_gnw.py")
MAME = r"C:\Users\dsalt\Downloads\mame\src\mame\handheld\hh_sm510.cpp"


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


def load_mame():
    t = open(MAME, encoding="utf-8", errors="ignore").read()

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


def parse_py_kb():
    """kb declared in shrink_gnw.py per game."""
    src = open(PY, encoding="utf-8").read()
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


def main():
    blocks = load_mame()
    if "--py" in sys.argv:
        print("== shrink_gnw.py vs MAME ==")
        sm5a_games = {"chef", "fire", "ball", "vermin", "helmet",
                      "octopus", "pchute", "popeye", "egg", "flagman",
                      "judge", "manholeg", "lion", "fires", "mmouse"}
        for g, kb in parse_py_kb().items():
            if g == "fire":
                continue  # FR-27: specific K filter (is_sm5a_keyboard in gw_system.c)
            cpu = "SM5A___" if g in sm5a_games else "SM511__"
            bad = check(kb, blocks, g, cpu)
            if bad:
                for slot, rn, exp, act in bad:
                    print("  !! %-9s kb[%d]=0x%08X  MAME %s=0x%08X"
                          % (g, slot, act, rn, exp))
        print("done")
        return

    print("== .gnw files in gnw/ vs MAME ==")
    nbad = 0
    for f in sorted(os.listdir(GNW)):
        if not f.endswith(".gnw"):
            continue
        g = f[4:-4]
        gw = open(os.path.join(GNW, f), "rb").read()
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


def game_cpu_sig(rom):
    """cpu_name and rom_signature of a .gnw."""
    return rom[0:8].decode("latin1").strip("\x00 "), rom[8:16].decode("latin1")


if __name__ == "__main__":
    main()


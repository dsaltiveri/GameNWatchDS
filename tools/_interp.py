# -*- coding: utf-8 -*-
"""SM510 interpreter in Python to analyze the firmware keyboard polling."""
import struct, sys, zipfile
from collections import Counter

rom = zipfile.ZipFile(r'c:\Users\dsalt\Downloads\GameNWatchDS\roms\gnw_dkong.zip').read('dk-52')

pc = prev_pc = op = prev_op = param = 0
acc = bl = bm = c = 0
sbm = sbl = skip = halt = False
w = s_out = r = r_out = 0
div = s1s = 0
clk_div = 2
stack = [0, 0]
stack_levels = 2
prgwidth = 12; datawidth = 7
prgmask = (1 << 12) - 1; datamask = (1 << 7) - 1
ram = [0] * 128
buttons = 0
kb_slots = [0] * 10
LOG = []

def bitmask(p): return 1 << (p & 3)

def ram_r():
    blh = 8 if sbl else 0
    bmh = (1 << (datawidth - 1)) if sbm else 0
    address = (bmh | blh | bm << 4 | bl) & datamask
    if stack_levels == 1 and address > 0x4f: address &= 0x4f
    return ram[address] & 0xf

def ram_w(d):
    blh = 8 if sbl else 0
    bmh = (1 << (datawidth - 1)) if sbm else 0
    address = (bmh | blh | bm << 4 | bl) & datamask
    if stack_levels == 1 and address > 0x4f: address &= 0x4f
    ram[address] = d & 0xf

def pop_stack():
    global pc
    pc = stack[0] & prgmask
    for i in range(stack_levels - 1): stack[i] = stack[i + 1]

def push_stack():
    for i in range(stack_levels - 1, 0, -1): stack[i] = stack[i - 1]
    stack[0] = pc

def do_branch(pu, pm, pl):
    global pc
    pc = ((pu << 10) | (pm << 6 & 0x3c0) | (pl & 0x3f)) & prgmask

def increment_pc():
    global pc
    feed = 0 if ((pc >> 1 ^ pc) & 1) else 0x20
    pc = feed | (pc >> 1 & 0x1f) | (pc & ~0x3f)

def m_read_k():
    io_K = 0
    kp = buttons & 0xff
    for Sx in range(8):
        if (s_out >> Sx) & 1:
            k = kb_slots[Sx]
            if (k & 0x000000ff) & kp: io_K |= 0x1
            if (k & 0x0000ff00) & (kp << 8): io_K |= 0x2
            if (k & 0x00ff0000) & (kp << 16): io_K |= 0x4
            if (k & 0xff000000) & (kp << 24): io_K |= 0x8
    return io_K


def exec_one():
    global pc, op, prev_op, param, acc, bl, bm, sbm, sbl, c, skip
    global w, s_out, r, halt, div, s1s, ram

    if 0x20 <= op < 0x30:  # LAX
        if (op & ~0xf) != (prev_op & ~0xf):
            acc = op & 0xf
    elif 0x30 <= op < 0x40:  # ADX
        acc += (op & 0xf)
        skip = ((op & 0xf) != 10 and (acc & 0x10) != 0)
        acc &= 0xf
    elif 0x40 <= op < 0x50:  # LB
        bm = (bm & 4) | (op & 3)
        bl = (op >> 2 & 3) | (0xc if (op & 0xc) else 0)
    elif 0x80 <= op < 0xc0:  # T
        pc = (pc & ~0x3f) | (op & 0x3f)
    elif op >= 0xc0:  # TM
        idx = rom[op & 0x3f]
        push_stack()
        do_branch(idx >> 6 & 3, 4, idx & 0x3f)
    else:
        if 0x04 <= op <= 0x07: ram_w(ram_r() & ~bitmask(op))            # RM
        elif 0x0c <= op <= 0x0f: ram_w(ram_r() | bitmask(op))           # SM
        elif 0x10 <= op <= 0x13:                                        # EXC
            a = acc; acc = ram_r(); ram_w(a); bm ^= (op & 3)
        elif 0x14 <= op <= 0x17:                                        # EXCI
            a = acc; acc = ram_r(); ram_w(a); bm ^= (op & 3)
            bl = (bl + 1) & 0xf; skip = (bl == 0)
        elif 0x18 <= op <= 0x1b: acc = ram_r(); bm ^= (op & 3)          # LDA
        elif 0x1c <= op <= 0x1f:                                        # EXCD
            a = acc; acc = ram_r(); ram_w(a); bm ^= (op & 3)
            bl = (bl - 1) & 0xf; skip = (bl == 0xf)
        elif 0x54 <= op <= 0x57: skip = ((ram_r() & bitmask(op)) != 0)  # TMI
        else:
            if op == 0x00: pass
            elif op == 0x01: pass  # ATBP
            elif op == 0x02: sbm = True
            elif op == 0x03: pc = (pc & ~0xf) | acc                      # ATPL
            elif op == 0x08: acc = (acc + ram_r()) & 0xf                # ADD
            elif op == 0x09:                                            # ADD11
                acc += ram_r() + c
                c = acc >> 4 & 1; skip = (c == 1); acc &= 0xf
            elif op == 0x0a: acc ^= 0xf                                 # COMA
            elif op == 0x0b: a = acc; acc = bl; bl = a                  # EXBLA
            elif op == 0x50 or op == 0x5e: skip = True                  # TB / TAL (stub: pin high)
            elif op == 0x51: skip = not c                               # TC
            elif op == 0x52: skip = (acc == ram_r())                    # TAM
            elif op == 0x53 or op == 0x58:                              # TIS
                skip = not s1s; s1s = False
            elif op == 0x59 or op == 0x60: pass                         # ATL / ATFC
            elif op == 0x5a: skip = (acc == 0)                          # TA0
            elif op == 0x5b: skip = (acc == bl)                         # TABL
            elif op == 0x5d: halt = True                                # CEND
            elif op == 0x5f: bl = param & 0xf; bm = (param & datamask) >> 4  # LBL
            elif op == 0x61: r = acc                                    # ATR
            elif op == 0x62: w = w << 1 | 0; s_out = w                  # WR
            elif op == 0x63: w = w << 1 | 1; s_out = w                  # WS
            elif op == 0x64: bl = (bl + 1) & 0xf; skip = (bl == 0)      # INCB
            elif op == 0x65: div = 0                                    # IDIV
            elif op == 0x66: c = 0                                      # RC
            elif op == 0x67: c = 1                                      # SC
            elif op == 0x68: skip = ((div & 0x4000) != 0)               # TF1
            elif op == 0x69: skip = ((div & 0x0800) != 0)               # TF4
            elif op == 0x6a:                                            # KTA
                k = m_read_k(); LOG.append((s_out, k)); acc = k
            elif op == 0x6b:                                            # ROT
                cc = acc & 1; acc = acc >> 1 | (c << 3); c = cc
            elif op == 0x6c: bl = (bl - 1) & 0xf; skip = (bl == 0xf)    # DECB
            elif op == 0x6e: pop_stack()                                # RTN0
            elif op == 0x6f: pop_stack(); skip = True                   # RTN1
            elif op == 0x7c: push_stack(); do_branch(param >> 6 & 3, op & 3, param & 0x3f)  # TML
            elif 0x70 <= op <= 0x7f: do_branch(param >> 6 & 3, op & 0xf, param & 0x3f)      # TL
            else:
                print('illegal opcode %02X at %04X' % (op, prev_pc)); sys.exit(1)
    sbm = (op == 0x02)

def reset():
    global pc, prev_pc, op, prev_op, acc, bl, bm, sbm, sbl, c, skip
    global w, s_out, r, r_out, halt, div, s1s, ram, stack, k_active
    skip = False; halt = False; sbl = False; sbm = False
    op = prev_op = 0
    do_branch(3, 7, 0)
    prev_pc = pc
    r = r_out = 0
    ram = [0] * 128; stack = [0, 0]
    k_active = False; div = 0; s1s = False

def div_timer(nb):
    global div, s1s
    old = div
    div = (div + nb) & 0x7fff
    if div < old:
        s1s = True

def run(max_instr):
    global pc, prev_pc, op, prev_op, param, skip, icount
    global halt, k_active, s1s, clk_div
    remaining = max_instr
    nwake = 0
    ntrace = 0
    dump_done = True
    while max_instr > 0:
        max_instr -= 1
        if halt:
            div_timer(clk_div * remaining)
            if not (k_active or s1s):
                return
            halt = False
            do_branch(1, 0, 0)  # wakeup vector
            s1s = False
            nwake += 1
            remaining = max_instr
            continue
        prev_op = op
        prev_pc = pc
        op = rom[pc]
        increment_pc()
        if op == 0x5f or (op & 0xf0) == 0x70:
            param = rom[pc]; increment_pc()
        if skip:
            skip = False; op = 0
        if not dump_done and 0x300 <= prev_pc < 0x400:
            print('  ENTRY to page 3 at instr %d pc=%04X' % (ntrace, prev_pc))
            dump_done = True
        if not dump_done and ntrace < 400:
            print('  [%4d] pc=%04X op=%02X acc=%X bl=%X' % (ntrace, prev_pc, op, acc, bl))
        ntrace += 1
        exec_one()
        div_timer(clk_div * (remaining - max_instr))
        remaining = max_instr
        k_active = (m_read_k() != 0)

def run_buttons(btn, kb, max_instr=5000000):
    global buttons, kb_slots, LOG
    kb_slots = kb; buttons = btn; LOG = []
    reset(); run(max_instr)
    return LOG

def main():
    import os
    game = sys.argv[1] if len(sys.argv) > 1 else 'dkong'
    zpath = os.path.join(r'c:\Users\dsalt\Downloads\GameNWatchDS\roms', 'gnw_%s.zip' % game)
    entry = {'dkong': 'dk-52', 'bfight': 'bf-803.program', 'boxing': 'bx-301_744.program',
             'rshower': 'lp-57', 'smb': 'ym-801.program', 'zelda': 'zl-65.program',
             'ball': 'ac-01', 'chef': 'cn-20'}.get(game)
    with zipfile.ZipFile(zpath) as z:
        cand = [n for n in z.namelist() if 'melody' not in n.lower() and n.lower().endswith(('.program', '.bin'))]
        if not cand:
            cand = [n for n in z.namelist() if '.' not in n and 'svg' not in n.lower()]
        rom0 = z.read(cand[0])
    global rom
    rom = rom0
    print('ROM %s: %s (%d bytes)' % (game, cand[0], len(rom)))

    gw = open(os.path.join(r'c:\Users\dsalt\Downloads\GameNWatchDS\gnw', 'gnw_%s.gnw' % game), 'rb').read()
    okb = struct.unpack_from('<I', gw, 92)[0]
    kb_actual = [struct.unpack_from('<I', gw, okb + 4 * i)[0] for i in range(10)]

    print('kb slot0=%08X slot1=%08X' % (kb_actual[0], kb_actual[1]))
    # GW_BUTTON_* values from gw_system.h: UP=0x02, RIGHT=0x04.
    names = {'UP': 0x02, 'RIGHT': 0x04, 'LEFT': 0x01, 'DOWN': 0x08, 'GAME': 0x80, 'NONE': 0}
    for bname, bval in names.items():
        LOG = run_buttons(bval, kb_actual)
        cnt = Counter(LOG)
        top = cnt.most_common(6)
        print('  %-5s: KTA=%d %s' % (bname, len(LOG),
              ' | '.join('S=%X->K=%X x%d' % (s, k, n) for (s, k), n in top)))

main()



# -*- coding: utf-8 -*-
"""Disassembles an SM510 ROM and shows the keyboard polling sequence."""
import sys, zipfile

# SM510 opcode map (sm510core.c)
def disasm1(rom):
    """Returns a list of (pc, mnem, bytes)."""
    out = []
    pc = 0
    n = len(rom)
    while pc < n:
        op = rom[pc]
        mnem = None
        size = 1
        # 2-byte opcodes
        if op == 0x5f:
            mnem = 'LBL #%02X' % rom[pc + 1]; size = 2
        elif 0x70 <= op <= 0x7f:
            mnem = 'TL %02X%02X' % (op & 0xf, rom[pc + 1]); size = 2
        else:
            mnem = TBL.get(op, '?? %02X' % op)
        out.append((pc, mnem, rom[pc:pc + size]))
        pc += size
    return out

TBL = {
    0x00: 'SKIP', 0x01: 'ATBP', 0x02: 'SBM', 0x03: 'ATPL',
    0x08: 'ADD', 0x09: 'ADD11', 0x0a: 'COMA', 0x0b: 'EXBLA',
    0x50: 'TB', 0x51: 'TC', 0x52: 'TAM', 0x53: 'TIS',
    0x58: 'TIS', 0x59: 'ATL', 0x5a: 'TA0', 0x5b: 'TABL',
    0x5d: 'CEND', 0x5e: 'TAL', 0x5f: 'LBL',
    0x60: 'ATFC', 0x61: 'ATR', 0x62: 'WR', 0x63: 'WS',
    0x64: 'INCB', 0x65: 'IDIV', 0x66: 'RC', 0x67: 'SC',
    0x68: 'TF1', 0x69: 'TF4', 0x6a: 'KTA', 0x6b: 'ROT',
    0x6c: 'DECB', 0x6d: 'BDC', 0x6e: 'RTN0', 0x6f: 'RTN1',
}
for i in range(0x04, 0x08): TBL[i] = 'RM'
for i in range(0x0c, 0x10): TBL[i] = 'SM'
for i in range(0x10, 0x14): TBL[i] = 'EXC'
for i in range(0x14, 0x18): TBL[i] = 'EXCI'
for i in range(0x18, 0x1c): TBL[i] = 'LDA'
for i in range(0x1c, 0x20): TBL[i] = 'EXCD'
for i in range(0x20, 0x30): TBL[i] = 'LAX'
for i in range(0x30, 0x40): TBL[i] = 'ADX'
for i in range(0x40, 0x50): TBL[i] = 'LB'
for i in range(0x54, 0x58): TBL[i] = 'TMI'
for i in range(0x80, 0xc0): TBL[i] = 'T'
for i in range(0xc0, 0x100): TBL[i] = 'TM'

def main():
    zpath = r'c:\Users\dsalt\Downloads\GameNWatchDS\roms\gnw_dkong.zip'
    with zipfile.ZipFile(zpath) as z:
        rom = z.read('dk-52')
    print('ROM dk-52 size:', len(rom))
    lines = disasm1(rom)
    # show polling sequences: find WS/WR ... KTA
    # and also the full disassembly around the KTA instructions
    ktas = [i for i, (pc, mnem, b) in enumerate(lines) if mnem == 'KTA']
    print('KTA at:', [lines[i][0] for i in ktas][:30])
    # dump the 12 instructions around each KTA (the 5 preceding ones)
    seen = set()
    for i in ktas:
        start = max(0, i - 6)
        for j in range(start, min(len(lines), i + 4)):
            if j in seen:
                continue
            seen.add(j)
            pc, mnem, b = lines[j]
            print('  %04X: %s' % (pc, mnem))
        print('  ----')
    # full dump to see the main flow (first 512 instructions)
    print('\n=== dump of the first 400 instructions ===')
    for pc, mnem, b in lines[:400]:
        print('%04X: %s' % (pc, mnem))

main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Builds the self-contained .gnw files of GameNWatchDS straight from the
source ZIPs (no intermediate assets in the repo):

  shrinker/input/roms/gnw_<game>.zip      -> SM5xx binary ROM + segment SVGs
  shrinker/input/artwork/gnw_<game>.zip   -> scene PNGs used to compose the backdrops

Each .gnw contains: program, LCD geometry, keyboard table and the TWO RGB565
backdrops (topNS + bottomNS) in the background_pixel object. Segments are
rendered with Inkscape (like the original converters) and the backdrops are
composed with Pillow using BLACK strips on every game.

Usage:
    python shrinker/shrink_gnw.py                 # builds gnw/gnw_*.gnw
    python shrinker/shrink_gnw.py --only fire     # a single game
    python shrinker/shrink_gnw.py --force         # re-render segments (no cache)

The CASE previews (render_preview_case and helpers) now live in
shrinker/build_gnw_case.py; this script only handles the .gnw files and the
backdrop+segment preview (render_preview).
"""
import hashlib
import io
import json
import os
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GNW_DIR = os.path.join(ROOT, "shrinker", "output", "gnw")
SRC_DIR = os.path.join(ROOT, "shrinker", "build")
INKSCAPE = r"C:\Program Files\Inkscape\bin\inkscape.com"

W, H_DS = 256, 192


def _q8(v):
    """Quantizes a channel to 5 bits rounding to the nearest neighbor (like shrink_it.py)."""
    p = round(v / 8.0) * 8
    return (255 if p > 255 else p) // 8


def to_nds_bmp16(img):
    """Converts an image to the NDS 16bpp framebuffer format (Bmp16):
    0x8000 | (B5 << 10) | (G5 << 5) | R5  (bit15 = opaque, like grit)."""
    out = bytearray()
    for r, g, b in img.convert("RGB").getdata():
        out += struct.pack("<H", 0x8000 | (_q8(b) << 10) | (_q8(g) << 5) | (_q8(r)))
    return bytes(out)


def flatten_alpha(art, png):
    """Composites the alpha channel of a PNG over a white background and
    returns RGB.

    Replicates the LCD-Game-Shrinker (shrink_it.py) chain:
      img_background = Image.new("RGBA", png.size, (255, 255, 255))
      alpha_composite = Image.alpha_composite(img_background, png).convert('RGB')
    Done at the original size, BEFORE any resizing."""
    im = Image.open(io.BytesIO(art[png])).convert("RGBA")
    base = Image.new("RGBA", im.size, (255, 255, 255))
    return Image.alpha_composite(base, im).convert("RGB")


def flatten_reflector(img, threshold=25, y0=None, y1=None):
    # Flattens the backdrop reflector (the greyish layer behind the LCD) to a
    # single uniform color. The artwork brings it as a lighting gradient;
    # the histogram mode (~95%% of the backdrop) is taken and close pixels
    # (euclidean distance < threshold) are replaced by its mean. Black and
    # distant details are left untouched.
    #
    # y0/y1 (optional) restrict the flattening to those rows [y0, y1). Used
    # on bg_view games where only the top strip is a grey reflector and the
    # color bands below are flattened separately with flatten_bands.
    img = img.convert("RGB")
    w, h = img.size
    if y0 is None:
        y0 = 0
    if y1 is None:
        y1 = h
    y0 = max(0, y0); y1 = min(h, y1)
    px = img.load()
    cnt = {}
    for y in range(y0, y1):
        for x in range(w):
            c = px[x, y]
            cnt[c] = cnt.get(c, 0) + 1
    if not cnt:
        return img
    rr, rg, rb = max(cnt, key=cnt.get)
    t2 = threshold * threshold
    sr = sg = sb = n = 0
    for y in range(y0, y1):
        for x in range(w):
            r, g, b = px[x, y]
            d = (r - rr) ** 2 + (g - rg) ** 2 + (b - rb) ** 2
            if d < t2:
                sr += r; sg += g; sb += b; n += 1
    if n == 0:
        return img
    mr, mg, mb = sr // n, sg // n, sb // n
    for y in range(y0, y1):
        for x in range(w):
            r, g, b = px[x, y]
            d = (r - rr) ** 2 + (g - rg) ** 2 + (b - rb) ** 2
            if d < t2:
                px[x, y] = (mr, mg, mb)
    return img


def flatten_bands(img, axis, limits, threshold=25):
    """Flattens each band (color strip) to its local mean color instead of
    using a global mode. axis=0: bands by column (vertical); axis=1: by
    row (horizontal). Within each band, pixels close to its mode
    (distance < threshold) are replaced by that band's mean; the artwork
    (far from the mode) is preserved."""
    img = img.convert("RGB")
    w, h = img.size
    px = img.load()
    t2 = threshold * threshold
    for b in range(len(limits) - 1):
        lo, hi = limits[b], limits[b + 1]
        if axis == 0:  # columns [lo,hi)
            xs, ys = range(lo, min(hi, w)), range(h)
        else:          # rows [lo,hi)
            xs, ys = range(w), range(lo, min(hi, h))
        if not xs or not ys:
            continue
        cnt = {}
        for y in ys:
            for x in xs:
                c = px[x, y]
                cnt[c] = cnt.get(c, 0) + 1
        rr, rg, rb = max(cnt, key=cnt.get)
        sr = sg = sb = n = 0
        for y in ys:
            for x in xs:
                r, g, b = px[x, y]
                if (r - rr) ** 2 + (g - rg) ** 2 + (b - rb) ** 2 < t2:
                    sr += r; sg += g; sb += b; n += 1
        if n == 0:
            continue
        mr, mg, mb = sr // n, sg // n, sb // n
        for y in ys:
            for x in xs:
                r, g, b = px[x, y]
                if (r - rr) ** 2 + (g - rg) ** 2 + (b - rb) ** 2 < t2:
                    px[x, y] = (mr, mg, mb)
    return img


def compose_view(art, view):
    # Composites the backdrop according to a .lay view (layers with bounds,
    # blend and alpha) over a view["w"]xview["h"] canvas. blends: None (over),
    # multiply, add. Returns a PIL RGB Image of the composed canvas.
    W, H = view["w"], view["h"]
    acc = np.zeros((H, W, 3), dtype=np.float64)
    for i, (png, (x, y, w, h), blend, alpha) in enumerate(view["layers"]):
        # same composition as compose_bg: the 1st layer is flattened over white.
        if i == 0:
            im = flatten_alpha(art, png).convert("RGBA")
        else:
            im = Image.open(io.BytesIO(art[png])).convert("RGBA")
        # same scaling pipeline as the Background (compose_bg): resize to
        # the .lay backdrop and then to the layer rect.
        if view.get("mame"):
            im = im.resize(tuple(view["mame"]), Image.LANCZOS)
        im = im.resize((w, h), Image.LANCZOS)
        la = np.zeros((H, W, 4), dtype=np.float64)
        if 0 <= x < W and 0 <= y < H:
            x1 = min(x + w, W); y1 = min(y + h, H)
            la[y:y1, x:x1] = np.asarray(im.resize((x1 - x, y1 - y), Image.LANCZOS), dtype=np.float64)
        aeff = (la[..., 3] / 255.0) * alpha
        rgb = la[..., :3]
        a3 = aeff[..., None]
        if blend == "multiply":
            acc = acc * (1 - a3) + (acc * rgb / 255.0) * a3
        elif blend == "add":
            acc = acc * (1 - a3) + (acc + rgb) * a3
        else:
            acc = acc * (1 - a3) + rgb * a3
    acc = np.clip(acc, 0, 255).astype(np.uint8)
    return Image.fromarray(acc)


def compose_bg(art, bg_top, bg_bottom, kind, bg_fit=None, lcd_h=165,
               reflector=None, mame=None, view=None):
    """Composes topNS/bottomNS (256x192) from the artwork PNGs and returns
    them in NDS Bmp16 format. kind='fire' uses BackgroundNS at 256x163
    centered; kind='dual' uses two 256x165 scenes with black strips.
    lcd_h is the LCD height (default SCENE_H=165). Like LCD-Game-Shrinker
    with keep_aspect_ratio=False, the backdrop is stretched to fill the
    LCD (W x lcd_h) without side margins, aligned with the vertical
    position of the segments.

    bg_fit (dict w/h/x/y) changes the destination rect in 'single' to keep
    the artwork aspect ratio (fit='w' or 'h' in the config): the backdrop
    is stretched to the contained rect and centered, and the segments use
    the same uniform scale (see _rescale_svg_to_target)."""
    mame_top = mame.get("bg_top") if mame else None
    mame_bot = mame.get("bg_bottom") if mame else None

    if view:
        # Per-view composition: composites the backdrop and stretches/centers it on the LCD.
        comp = compose_view(art, view)
        if view.get("bands"):
            b = view["bands"]
            comp = flatten_bands(comp, b["axis"], b["limits"])
        elif reflector:
            comp = flatten_reflector(comp, reflector)
        # Top strip of grey reflector (no color bands): flattened separately
        # with flatten_reflector restricted to those rows.
        rtop = view.get("reflector_top")
        if rtop:
            comp = flatten_reflector(comp, reflector, 0, rtop)
        rect = (bg_fit or {}).get("bottom")
        if rect:
            comp = comp.resize((rect["w"], rect["h"]), Image.LANCZOS)
            bot = Image.new("RGB", (W, H_DS), (0, 0, 0))
            bot.paste(comp, (rect["x"], rect["y"]))
        else:
            comp = comp.resize((W, lcd_h), Image.LANCZOS)
            bot = Image.new("RGB", (W, H_DS), (0, 0, 0))
            bot.paste(comp, (0, (H_DS - lcd_h) // 2))
        top = Image.new("RGB", (W, H_DS), (0, 0, 0))
        return to_nds_bmp16(top), to_nds_bmp16(bot)
    if kind in ("single", "fire"):
        # Single screen: backdrop stretched to fill the LCD (W x lcd_h) and
        # vertically centered (y=(192-lcd_h)/2, the segment offset).
        # Like LCD-Game-Shrinker (keep_aspect_ratio=False). bg_bottom can be
        # a str or a list (base + overlays with alpha).
        top = Image.new("RGB", (W, H_DS), (0, 0, 0))
        bot = Image.new("RGB", (W, H_DS), (0, 0, 0))
        layers = bg_bottom if isinstance(bg_bottom, list) else [bg_bottom]
        comp = None
        rect = (bg_fit or {}).get("bottom")
        for i, png in enumerate(layers):
            if i == 0:
                im = flatten_alpha(art, png)
            else:
                im = Image.open(io.BytesIO(art[png])).convert("RGBA")
            if mame_bot:
                im = im.resize(mame_bot, Image.LANCZOS)
            if rect:
                im = im.resize((rect["w"], rect["h"]), Image.LANCZOS)
            else:
                im = im.resize((W, lcd_h), Image.LANCZOS)
            if comp is None:
                comp = im.convert("RGB")
            else:
                comp = Image.alpha_composite(
                    comp.convert("RGBA"), im.convert("RGBA")).convert("RGB")
        if reflector:
            comp = flatten_reflector(comp, reflector)
        if rect:
            bot.paste(comp, (rect["x"], rect["y"]))
        else:
            bot.paste(comp, (0, (H_DS - lcd_h) // 2))
    else:
        # Dual: each half stretched to fill the LCD (bezel cropped).
        top = Image.new("RGB", (W, H_DS), (0, 0, 0))
        top_img = flatten_alpha(art, bg_top)
        if mame_top:
            top_img = top_img.resize(mame_top, Image.LANCZOS)
        trect = (bg_fit or {}).get("top")
        if trect:
            tsize = (trect["w"], trect["h"]); tpos = (trect["x"], trect["y"])
        else:
            tsize = (W, lcd_h); tpos = (0, 0)
        if reflector:
            top_img = flatten_reflector(top_img.resize(tsize, Image.LANCZOS), reflector)
        else:
            top_img = top_img.resize(tsize, Image.LANCZOS)
        top.paste(top_img, tpos)
        bot = Image.new("RGB", (W, H_DS), (0, 0, 0))
        bot_img = flatten_alpha(art, bg_bottom)
        if mame_bot:
            bot_img = bot_img.resize(mame_bot, Image.LANCZOS)
        brect = (bg_fit or {}).get("bottom")
        if brect:
            bsize = (brect["w"], brect["h"]); bpos = (brect["x"], brect["y"])
        else:
            bsize = (W, lcd_h); bpos = (0, 0)
        if reflector:
            bot_img = flatten_reflector(bot_img.resize(bsize, Image.LANCZOS), reflector)
        else:
            bot_img = bot_img.resize(bsize, Image.LANCZOS)
        bot.paste(bot_img, bpos)
    return to_nds_bmp16(top), to_nds_bmp16(bot)


# ---------------------------------------------------------------------------
# Per-game configuration (values taken from the build_*.py / convert_*.py)
# ---------------------------------------------------------------------------
GAMES = {
    "dkong2": {
        "rom_zip": "shrinker/input/roms/gnw_dkong2.zip", "art_zip": "shrinker/input/artwork/gnw_dkong2.zip",
        "rom_entry": "jr-55_560",
        "cpu": b"SM510__\x00", "sig": b"w_dkong2", "flags": 0x52,
        # JR-55 keyboard table (MAME hh_sm510.cpp INPUT_PORTS_START(gnw_dkong2)):
        # S1=JUMP(A), S2=d-pad (K1=RIGHT K2=UP K3=LEFT K4=DOWN), S3=menu
        # (Time/GameB/GameA/Alarm). Pure MAME: K1=RIGHT, K2=UP.
        "kb": [0x10000000, 0x08010204, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("bottom", "gnw_dkong2_bottom.svg", 1962, 1269, lambda ry: 192 + ry),
            ("top",    "gnw_dkong2_top.svg",    1962, 1269, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-TopNS.png", "bg_bottom": "Screen-BottomNS.png",
    },
    "fire": {
        "rom_zip": "shrinker/input/roms/gnw_fire.zip", "art_zip": "shrinker/input/artwork/gnw_fire.zip",
        "rom_entry": "fr-27",
        "cpu": b"SM5A___\x00", "sig": b"w_fire__", "flags": 0x92,
        "kb": [0x00802040, 0x00802040, 0x00802040, 0x00802040,
               0, 0, 0, 0, 0x00000001, 0x00000004],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,    # SM5A
        "screens": [
            ("main", "gnw_fire.svg", 3834, 2550, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
    },
    "lboat": {
        "rom_zip": "shrinker/input/roms/gnw_lboat.zip", "art_zip": "shrinker/input/artwork/gnw_lboat.zip",
        "rom_entry": "tc-58",
        "cpu": b"SM510__\x00", "sig": b"w_lboat_", "flags": 0x54,
        "kb": [0x00000401, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("right", "gnw_lboat_right.svg", 3689, 2583, lambda ry: 192 + ry),
            ("left",  "gnw_lboat_left.svg",  3795, 2583, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-LeftNS.png", "bg_bottom": "Screen-RightNS.png",
    },
    "mickdon": {
        "rom_zip": "shrinker/input/roms/gnw_mickdon.zip", "art_zip": "shrinker/input/artwork/gnw_mickdon.zip",
        "rom_entry": "dm-53_565",
        "cpu": b"SM510__\x00", "sig": b"w_mickdo", "flags": 0x54,
        "kb": [0x08010204, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("bottom", "gnw_mickdon_bottom.svg", 1962, 1269, lambda ry: 192 + ry),
            ("top",    "gnw_mickdon_top.svg",    1962, 1269, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-Top.png", "bg_bottom": "Screen-BottomNS.png",
    },
    "smbn": {
        "rom_zip": "shrinker/input/roms/gnw_smbn.zip", "art_zip": "shrinker/input/artwork/gnw_smbn.zip",
        "rom_entry": "ym-105.program",
        "melody_entry": "ym-105.melody",
        "cpu": b"SM511__\x00", "sig": b"w_smbn__", "flags": 0x52,
        # YM-105 keyboard table (MAME hh_sm510.cpp, INPUT_PORTS_START(gnw_smb)):
        #   S1 (kb[0]) = Time/GAME/Alarm (soft), WITHOUT Game B (only GAME exists)
        #   S2 (kb[1]) = D-pad UP/RIGHT/DOWN/LEFT
        #   S3 (kb[2]) = Jump (A)
        "kb": [0x00A08040, 0x01080402, 0x00000010, 0, 0, 0, 0, 0, 0, 0],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511 (same layout A/B/C+bs)
        "screens": [
            ("main", "gnw_smbn.svg", 3491, 2248, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
    },
    "ball": {
        "rom_zip": "shrinker/input/roms/gnw_ball.zip", "art_zip": "shrinker/input/artwork/gnw_ball.zip",
        "rom_entry": "ac-01",
        "cpu": b'SM5A___\x00', "sig": b'w_ball__', "flags": 0x92,
        "kb": [0x00000000, 0x00802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000004, 0x00000001],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_ball.svg", 3268, 2112, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": ["Background.png", "Background2NS.png"],
        "bg_reflector": 25,
        },
    "fires": {
        "rom_zip": "shrinker/input/roms/gnw_fires.zip", "art_zip": "shrinker/input/artwork/gnw_fires.zip",
        "rom_entry": "rc-04",
        "cpu": b'SM5A___\x00', "sig": b'w_fire_s', "flags": 0x92,
        "kb": [0x00000000, 0x00802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000004, 0x00000001],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_fires.svg", 3273, 2148, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "Background.png",

        },
    "vermin": {
        "rom_zip": "shrinker/input/roms/gnw_vermin.zip", "art_zip": "shrinker/input/artwork/gnw_vermin.zip",
        "rom_entry": "mt-03",
        "cpu": b'SM5A___\x00', "sig": b'w_vermin', "flags": 0x52,
        "kb": [0x00000000, 0x00802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000004, 0x00000001],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_vermin.svg", 3378, 2211, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": ["Background.png", "Background2NS.png"],
        },
    "helmet": {
        "rom_zip": "shrinker/input/roms/gnw_helmet.zip", "art_zip": "shrinker/input/artwork/gnw_helmet.zip",
        "rom_entry": "cn-17",
        "cpu": b'SM5A___\x00', "sig": b'w_helmet', "flags": 0x92,
        "kb": [0x00000000, 0x00000000, 0x00000000, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000004, 0x00000001],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_helmet.svg", 3342, 2178, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "HelmetNS.png",
        },
    "octopus": {
        "rom_zip": "shrinker/input/roms/gnw_octopus.zip", "art_zip": "shrinker/input/artwork/gnw_octopus.zip",
        "rom_entry": "oc-22",
        "cpu": b'SM5A___\x00', "sig": b'w_octopu', "flags": 0x92,
        "kb": [0x00000000, 0x00000000, 0x00000000, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000004, 0x00000001],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_octopus.svg", 3867, 2634, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "pchute": {
        "rom_zip": "shrinker/input/roms/gnw_pchute.zip", "art_zip": "shrinker/input/artwork/gnw_pchute.zip",
        "rom_entry": "pr-21",
        "cpu": b'SM5A___\x00', "sig": b'w_parach', "flags": 0x92,
        "kb": [0x00000000, 0x00000000, 0x00000000, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000004, 0x00000001],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_pchute.svg", 3711, 2502, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "popeye": {
        "rom_zip": "shrinker/input/roms/gnw_popeye.zip", "art_zip": "shrinker/input/artwork/gnw_popeye.zip",
        "rom_entry": "pp-23",
        "cpu": b'SM5A___\x00', "sig": b'w_popeye', "flags": 0x92,
        "kb": [0x00000000, 0x00000000, 0x00000000, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000004, 0x00000001],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_popeye.svg", 3858, 2597, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "popeyep": {
        "rom_zip": "shrinker/input/roms/gnw_popeyep.zip", "art_zip": "shrinker/input/artwork/gnw_popeyep.zip",
        "rom_entry": "pg-92.program",
            "melody_entry": "pg-92.melody",
        "cpu": b'SM511__\x00', "sig": b'w_popeye', "flags": 0x52,
        "kb": [0x00010410, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_popeyep.svg", 3764, 2046, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "Background.png",
        "lcd_inverted": True,
        "seg_method": "shrinker",
        # TIME clock (ADD_TIME from the LCD-Game-Shrinker custom):
        # hour=20/21, min=22/23, sec=24/25, PM value=8.
    },
    "chef": {
        "rom_zip": "shrinker/input/roms/gnw_chef.zip", "art_zip": "shrinker/input/artwork/gnw_chef.zip",
        "rom_entry": "fp-24",
        "cpu": b'SM5A___\x00', "sig": b'w_chef__', "flags": 0x92,
        "kb": [0x00000000, 0x00000000, 0x01040000, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_chef.svg", 5017, 3252, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "egg": {
        "rom_zip": "shrinker/input/roms/gnw_egg.zip", "art_zip": "shrinker/input/artwork/gnw_egg.zip",
        "rom_entry": "mc-25",
        "cpu": b'SM5A___\x00', "sig": b'w_egg___', "flags": 0x92,
        "kb": [0x00000000, 0x00000000, 0x02080401, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_egg.svg", 4008, 2562, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "flagman": {
        "rom_zip": "shrinker/input/roms/gnw_flagman.zip", "art_zip": "shrinker/input/artwork/gnw_flagman.zip",
        "rom_entry": "fl-02",
        "cpu": b'SM5A___\x00', "sig": b'w_flagma', "flags": 0x92,
        "kb": [0x00000000, 0x00000000, 0x0C090603, 0x00802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_flagman.svg", 3189, 2280, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "Background.png",
        },
    "judge": {
        "rom_zip": "shrinker/input/roms/gnw_judge.zip", "art_zip": "shrinker/input/artwork/gnw_judge.zip",
        "rom_entry": "ip-15",
        "cpu": b'SM5A___\x00', "sig": b'w_judge_', "flags": 0x92,
        "kb": [0x00000000, 0x00000000, 0x0309060C, 0x00802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_judge.svg", 3298, 2162, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "Background.png",
        },
    "lion": {
        "rom_zip": "shrinker/input/roms/gnw_lion.zip", "art_zip": "shrinker/input/artwork/gnw_lion.zip",
        "rom_entry": "ln-08",
        "cpu": b'SM5A___\x00', "sig": b'w_lion__', "flags": 0x92,
        "kb": [0x00000000, 0x00000000, 0x0309060C, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_lion.svg", 3306, 2169, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "manholeg": {
        "rom_zip": "shrinker/input/roms/gnw_manholeg.zip", "art_zip": "shrinker/input/artwork/gnw_manholeg.zip",
        "rom_entry": "mh-06",
        "cpu": b'SM5A___\x00', "sig": b'w_manhol', "flags": 0x92,
        "kb": [0x00000000, 0x00000000, 0x0309060C, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_manholeg.svg", 3266, 2116, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNSM.png",
        },
    "mmouse": {
        "rom_zip": "shrinker/input/roms/gnw_mmouse.zip", "art_zip": "shrinker/input/artwork/gnw_mmouse.zip",
        "rom_entry": "mc-25",
        "cpu": b'SM5A___\x00', "sig": b'w_mickey', "flags": 0x92,
        "kb": [0x00000000, 0x00000000, 0x0309060C, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 8 * a + 2 * b + c,   # SM5A
        "screens": [
            ("main", "gnw_mmouse.svg", 3957, 2538, lambda ry: 14 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "mmousep": {
        "rom_zip": "shrinker/input/roms/gnw_mmousep.zip", "art_zip": "shrinker/input/artwork/gnw_mmousep.zip",
        "rom_entry": "dc-95.program",
            "melody_entry": "dc-95.melody",
        "cpu": b'SM511__\x00', "sig": b'w_mmouse', "flags": 0x52,
        "kb": [0x00010400, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_mmousep.svg", 4008, 2343, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "Backgroundnew.png",
        "lcd_inverted": True,
        "seg_method": "shrinker",
        # TIME clock (ADD_TIME from the LCD-Game-Shrinker custom):
        # hour=20/21, min=22/23, sec=24/25, PM value=8.
    },
    "dkjr": {
        "rom_zip": "shrinker/input/roms/gnw_dkjr.zip", "art_zip": "shrinker/input/artwork/gnw_dkjr.zip",
        "rom_entry": "dj-101",
        "cpu": b'SM510__\x00', "sig": b'w_dkong_', "flags": 0x52,
        "kb": [0x10000000, 0x08010204, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("main", "gnw_dkjr.svg", 2089, 1370, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "dkjrp": {
        "rom_zip": "shrinker/input/roms/gnw_dkjrp.zip", "art_zip": "shrinker/input/artwork/gnw_dkjrp.zip",
        "rom_entry": "cj-93.program",
            "melody_entry": "cj-93.melody",
        "cpu": b'SM511__\x00', "sig": b'w_dkjrp_', "flags": 0x52,
        "kb": [0x10000000, 0x08010204, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_dkjrp.svg", 3828, 2084, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "Background.png",
        "lcd_inverted": True,
        "seg_method": "shrinker",
        # Clock RAM addresses (ADD_TIME from the gnw_dkjrp.py custom):
        # hour=20/21, min=22/23, sec=24/25, PM value=8.
    },
    "dkcirc": {
        "rom_zip": "shrinker/input/roms/gnw_dkcirc.zip", "art_zip": "shrinker/input/artwork/gnw_dkcirc.zip",
        "rom_entry": "mk-96.program",
            "melody_entry": "mk-96.melody",
        "cpu": b'SM511__\x00', "sig": b'w_dkcirc', "flags": 0x52,
        "kb": [0x00011400, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_dkcirc.svg", 4092, 2360, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "Background.png",
        "lcd_inverted": True,
        "seg_method": "shrinker",
        # TIME clock (ADD_TIME from the LCD-Game-Shrinker custom):
        # hour=20/21, min=22/23, sec=24/25, PM value=8.
    },
    "fireatk": {
        "rom_zip": "shrinker/input/roms/gnw_fireatk.zip", "art_zip": "shrinker/input/artwork/gnw_fireatk.zip",
        "rom_entry": "id-29",
        "cpu": b'SM510__\x00', "sig": b'w_fire_a', "flags": 0x52,
        "kb": [0x0903060C, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("main", "gnw_fireatk.svg", 4005, 2613, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "manhole": {
        "rom_zip": "shrinker/input/roms/gnw_manhole.zip", "art_zip": "shrinker/input/artwork/gnw_manhole.zip",
        "rom_entry": "nh-103",
        "cpu": b'SM510__\x00', "sig": b'w_manhol', "flags": 0x52,
        "kb": [0x0903060C, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("main", "gnw_manhole.svg", 3120, 2160, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "mariocm": {
        "rom_zip": "shrinker/input/roms/gnw_mariocm.zip", "art_zip": "shrinker/input/artwork/gnw_mariocm.zip",
        "rom_entry": "ml-102_577",
        "cpu": b'SM510__\x00', "sig": b'w_mcemen', "flags": 0x52,
        "kb": [0x00010410, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("main", "gnw_mariocm.svg", 1310, 859, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "mariocmt": {
        "rom_zip": "shrinker/input/roms/gnw_mariocmt.zip", "art_zip": "shrinker/input/artwork/gnw_mariocmt.zip",
        "rom_entry": "cm-72.program",
            "melody_entry": "cm-72.melody",
        "cpu": b'SM511__\x00', "sig": b'w_mcemen', "flags": 0x52,
        "kb": [0x00010410, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_mariocmt.svg", 3573, 1946, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "background2.png",
        "lcd_inverted": True,
        "seg_method": "shrinker",
        # TIME clock (ADD_TIME from the LCD-Game-Shrinker custom):
        # hour=20/21, min=22/23, sec=24/25, PM value=8.
    },
    "stennis": {
        "rom_zip": "shrinker/input/roms/gnw_stennis.zip", "art_zip": "shrinker/input/artwork/gnw_stennis.zip",
        "rom_entry": "sp-30",
        "cpu": b'SM510__\x00', "sig": b'w_snoopy', "flags": 0x52,
        "kb": [0x10000208, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("main", "gnw_stennis.svg", 3855, 2634, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "snoopyp": {
        "rom_zip": "shrinker/input/roms/gnw_snoopyp.zip", "art_zip": "shrinker/input/artwork/gnw_snoopyp.zip",
        "rom_entry": "sm-91.program",
            "melody_entry": "sm-91.melody",
        "cpu": b'SM511__\x00', "sig": b'w_snoopy', "flags": 0x52,
        "kb": [0x00010410, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_snoopyp.svg", 3748, 1991, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "Background.png",
        "lcd_inverted": True,
        "seg_method": "shrinker",
        # TIME clock (ADD_TIME from the LCD-Game-Shrinker custom):
        # hour=20/21, min=22/23, sec=24/25, PM value=8.
    },
    "tbridge": {
        "rom_zip": "shrinker/input/roms/gnw_tbridge.zip", "art_zip": "shrinker/input/artwork/gnw_tbridge.zip",
        "rom_entry": "tl-28",
        "cpu": b'SM510__\x00', "sig": b'w_turtle', "flags": 0x52,
        "kb": [0x01000004, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("main", "gnw_tbridge.svg", 3690, 2511, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "tfish": {
        "rom_zip": "shrinker/input/roms/gnw_tfish.zip", "art_zip": "shrinker/input/artwork/gnw_tfish.zip",
        "rom_entry": "tf-104",
        "cpu": b'SM510__\x00', "sig": b'w_tropic', "flags": 0x52,
        "kb": [0x00000401, 0xA0208040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("main", "gnw_tfish.svg", 3756, 2581, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "bfightn": {
        "rom_zip": "shrinker/input/roms/gnw_bfightn.zip", "art_zip": "shrinker/input/artwork/gnw_bfightn.zip",
        "rom_entry": "bf-107.program",
            "melody_entry": "bf-107.melody",
        "cpu": b'SM511__\x00', "sig": b'w_balloo', "flags": 0x52,
        "kb": [0x00A08040, 0x01080402, 0x00000010, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_bfightn.svg", 3567, 2487, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "climbern": {
        "rom_zip": "shrinker/input/roms/gnw_climbern.zip", "art_zip": "shrinker/input/artwork/gnw_climbern.zip",
        "rom_entry": "dr-106.program",
            "melody_entry": "dr-106.melody",
        "cpu": b'SM511__\x00', "sig": b'w_climbe', "flags": 0x52,
        "kb": [0x00A08040, 0x01080402, 0x00000010, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_climbern.svg", 6983, 4496, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "mariotj": {
        "rom_zip": "shrinker/input/roms/gnw_mariotj.zip", "art_zip": "shrinker/input/artwork/gnw_mariotj.zip",
        "rom_entry": "mb-108.program",
            "melody_entry": "mb-108.melody",
        "cpu": b'SM511__\x00', "sig": b'w_mario_', "flags": 0x52,
        "kb": [0x01000004, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_mariotj.svg", 3882, 2572, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNSm.png",
        },
    "mbaway": {
        "rom_zip": "shrinker/input/roms/gnw_mbaway.zip", "art_zip": "shrinker/input/artwork/gnw_mbaway.zip",
        "rom_entry": "tb-94.program",
            "melody_entry": "tb-94.melody",
        "cpu": b'SM511__\x00', "sig": b'w_mbaway', "flags": 0x52,
        "kb": [0x00010410, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_mbaway.svg", 3867, 2075, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "Background.png",
        "lcd_inverted": True,
        "seg_method": "shrinker",
        # TIME clock (ADD_TIME from the LCD-Game-Shrinker custom):
        # hour=20/21, min=22/23, sec=24/25, PM value=8.
    },
    "dkong": {
        "rom_zip": "shrinker/input/roms/gnw_dkong.zip", "art_zip": "shrinker/input/artwork/gnw_dkong.zip",
        "rom_entry": "dk-52",
        "cpu": b'SM510__\x00', "sig": b'w_donkey', "flags": 0x52,
        "kb": [0x10000000, 0x08010204, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("bottom", "gnw_dkong_bottom.svg", 3525, 2325, lambda ry: 192 + ry),
            ("top",    "gnw_dkong_top.svg", 3525, 2325, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-TopNS.png", "bg_bottom": "Screen-BottomNS.png",
        },
    "ghouse": {
        "rom_zip": "shrinker/input/roms/gnw_ghouse.zip", "art_zip": "shrinker/input/artwork/gnw_ghouse.zip",
        "rom_entry": "gh-54",
        "cpu": b'SM510__\x00', "sig": b'w_green_', "flags": 0x52,
        "kb": [0x10000000, 0x08010204, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("bottom", "gnw_ghouse_bottom.svg", 2812, 1866, lambda ry: 192 + ry),
            ("top",    "gnw_ghouse_top.svg", 2812, 1909, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-TopNS.png", "bg_bottom": "Screen-BottomNS.png",
        },
    "opanic": {
        "rom_zip": "shrinker/input/roms/gnw_opanic.zip", "art_zip": "shrinker/input/artwork/gnw_opanic.zip",
        "rom_entry": "op-51",
        "cpu": b'SM510__\x00', "sig": b'w_oil_pa', "flags": 0x52,
        "kb": [0x01000004, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("bottom", "gnw_opanic_bottom.svg", 3367, 2157, lambda ry: 192 + ry),
            ("top",    "gnw_opanic_top.svg", 3367, 2266, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-TopNS.png", "bg_bottom": "Screen-BottomNS.png",
        },
    "squish": {
        "rom_zip": "shrinker/input/roms/gnw_squish.zip", "art_zip": "shrinker/input/artwork/gnw_squish.zip",
        "rom_entry": "mg-61",
        "cpu": b'SM510__\x00', "sig": b'w_squish', "flags": 0x52,
        "kb": [0x01020408, 0xA0208040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("bottom", "gnw_squish_bottom.svg", 3393, 2274, lambda ry: 192 + ry),
            ("top",    "gnw_squish_top.svg", 3393, 2271, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-TopNS.png", "bg_bottom": "Screen-BottomNS.png",
        },
    "bjack": {
        "rom_zip": "shrinker/input/roms/gnw_bjack.zip", "art_zip": "shrinker/input/artwork/gnw_bjack.zip",
        "rom_entry": "bj-60.program",
            "melody_entry": "bj-60.melody",
        "cpu": b'SM512__\x00', "sig": b'w_black_', "flags": 0x52,
        "kb": [0x060C0903, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM512
        "screens": [
            ("bottom", "gnw_bjack_bottom.svg", 3189, 2154, lambda ry: 192 + ry),
            ("top",    "gnw_bjack_top.svg", 3189, 2142, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-TopNS.png", "bg_bottom": "Screen-BottomNS.png",
        },
    "bsweep": {
        "rom_zip": "shrinker/input/roms/gnw_bsweep.zip", "art_zip": "shrinker/input/artwork/gnw_bsweep.zip",
        "rom_entry": "bd-62.program",
            "melody_entry": "bd-62.melody",
        "cpu": b'SM512__\x00', "sig": b'w_bomb_s', "flags": 0x52,
        "kb": [0x08040201, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM512
        "screens": [
            ("bottom", "gnw_bsweep_bottom.svg", 4012, 2588, lambda ry: 192 + ry),
            ("top",    "gnw_bsweep_top.svg", 3999, 2688, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-TopNS.png", "bg_bottom": "Screen-BottomNS.png",
        },
    "gcliff": {
        "rom_zip": "shrinker/input/roms/gnw_gcliff.zip", "art_zip": "shrinker/input/artwork/gnw_gcliff.zip",
        "rom_entry": "mv-64.program",
            "melody_entry": "mv-64.melody",
        "cpu": b'SM512__\x00', "sig": b'w_gold_c', "flags": 0x52,
        "kb": [0x08040201, 0x00000010, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM512
        "screens": [
            ("bottom", "gnw_gcliff_bottom.svg", 3966, 2560, lambda ry: 192 + ry),
            ("top",    "gnw_gcliff_top.svg", 3864, 2529, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-TopNS.png", "bg_bottom": "Screen-BottomNS.png",
        },
    "pinball": {
        "rom_zip": "shrinker/input/roms/gnw_pinball.zip", "art_zip": "shrinker/input/artwork/gnw_pinball.zip",
        "rom_entry": "pb-59.program",
            "melody_entry": "pb-59.melody",
        "cpu": b'SM511__\x00', "sig": b'w_pinbal', "flags": 0x52,
        "kb": [0x00010400, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("bottom", "gnw_pinball_bottom.svg", 3372, 2259, lambda ry: 192 + ry),
            ("top",    "gnw_pinball_top.svg", 3513, 2326, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-TopNS.png", "bg_bottom": "Screen-BottomNS.png",
        },
    "sbuster": {
        "rom_zip": "shrinker/input/roms/gnw_sbuster.zip", "art_zip": "shrinker/input/artwork/gnw_sbuster.zip",
        "rom_entry": "jb-63.program",
            "melody_entry": "jb-63.melody",
        "cpu": b'SM511__\x00', "sig": b'w_safe_b', "flags": 0x52,
        "kb": [0x00000401, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("bottom", "gnw_sbuster_bottom.svg", 3891, 2571, lambda ry: 192 + ry),
            ("top",    "gnw_sbuster_top.svg", 3861, 2505, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-TopNS.png", "bg_bottom": "Screen-BottomNS.png",
        },
    "zelda": {
        "rom_zip": "shrinker/input/roms/gnw_zelda.zip", "art_zip": "shrinker/input/artwork/gnw_zelda.zip",
        "rom_entry": "zl-65.program",
            "melody_entry": "zl-65.melody",
        "cpu": b'SM512__\x00', "sig": b'w_zelda_', "flags": 0x52,
        "kb": [0x08040201, 0x00000010, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM512
        "screens": [
            ("bottom", "gnw_zelda_bottom.svg", 3711, 2495, lambda ry: 192 + ry),
            ("top",    "gnw_zelda_top.svg", 3711, 2601, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-TopNS.png", "bg_bottom": "Screen-BottomNS.png",
        },
    "mario": {
        "rom_zip": "shrinker/input/roms/gnw_mario.zip", "art_zip": "shrinker/input/artwork/gnw_mario.zip",
        "rom_entry": "mw-56",
        "cpu": b'SM510__\x00', "sig": b'w_mario_', "flags": 0x52,
        "kb": [0x08020401, 0xA0802040, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("right", "gnw_mario_right.svg", 3592, 2288, lambda ry: 192 + ry),
            ("left",  "gnw_mario_left.svg", 3505, 2235, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-LeftNS.png", "bg_bottom": "Screen-RightNS.png",
        "bg_reflector": 25,
        },
    "rshower": {
        "rom_zip": "shrinker/input/roms/gnw_rshower.zip", "art_zip": "shrinker/input/artwork/gnw_rshower.zip",
        "rom_entry": "lp-57",
        "cpu": b'SM510__\x00', "sig": b'w_rain_s', "flags": 0x52,
        "kb": [0x00104000, 0xA0802000, 0x08010204, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("right", "gnw_rshower_right.svg", 3724, 2499, lambda ry: 192 + ry),
            ("left",  "gnw_rshower_left.svg", 3690, 2499, lambda ry: 27 + ry),
        ],
        "bg_kind": "dual", "bg_top": "Screen-LeftNS.png", "bg_bottom": "Screen-RightNS.png",
        },
    "bfight": {
        "rom_zip": "shrinker/input/roms/gnw_bfight.zip", "art_zip": "shrinker/input/artwork/gnw_bfight.zip",
        "rom_entry": "bf-803.program", "melody_entry": "bf-803.melody",
        "cpu": b"SM511__\x00", "sig": b"w_bfight", "flags": 0x52,
        "kb": [0x00A08040, 0x01080402, 0x00000010, 0, 0, 0, 0, 0, 0, 0],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_bfight.svg", 3951, 2409, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "boxing": {
        "rom_zip": "shrinker/input/roms/gnw_boxing.zip", "art_zip": "shrinker/input/artwork/gnw_boxing.zip",
        "rom_entry": "bx-301_744.program", "melody_entry": "bx-301_744.melody",
        "cpu": b"SM511__\x00", "sig": b"w_boxing", "flags": 0x52,
        "kb": [0x00000000, 0x00000010, 0x00000000, 0x00000208, 0x00000000, 0x00000104, 0xA0802040, 0, 0, 0],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_boxing.svg", 3415, 932, lambda ry: 56 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "cgrab": {
        "rom_zip": "shrinker/input/roms/gnw_cgrab.zip", "art_zip": "shrinker/input/artwork/gnw_cgrab.zip",
        "rom_entry": "ud-202",
        "cpu": b"SM510__\x00", "sig": b"w_cgrab_", "flags": 0x52,
        "kb": [0x08010204, 0xA0802040, 0, 0, 0, 0, 0, 0, 0, 0],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("main", "gnw_cgrab.svg", 2084, 3696, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None,
        "bg_bottom": "Background.png",
        "bg_view": {
            "w": 256, "h": 165,
            "mame": [941, 1761],
            "reflector_top": 18,  # top grey reflector strip (0-17)
            "bands": {"axis": 0, "limits": [0, 64, 128, 192, 256]},  # strips by column
            "layers": [
                ["Background.png", [0, 0, 256, 165], None, 1.0],
                ["Subtract.png", [0, 0, 256, 165], "multiply", 1.0],
                ["Overlay.png", [0, 0, 256, 165], "add", 1.0],
                ["Lines.png", [0, 10, 256, 165], None, 0.2],  # offset y=10, height 165
                ["Frame2.png", [0, 0, 256, 165], None, 1.0],  # frame, keeps transparency
            ]
        },
        },
    "climber": {
        "rom_zip": "shrinker/input/roms/gnw_climber.zip", "art_zip": "shrinker/input/artwork/gnw_climber.zip",
        "rom_entry": "dr-802.program", "melody_entry": "dr-802.melody",
        "cpu": b"SM511__\x00", "sig": b"w_climbr", "flags": 0x52,
        "kb": [0x00A08040, 0x01080402, 0x00000010, 0, 0, 0, 0, 0, 0, 0],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_climber.svg", 3708, 2280, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "dkhockey": {
        "rom_zip": "shrinker/input/roms/gnw_dkhockey.zip", "art_zip": "shrinker/input/artwork/gnw_dkhockey.zip",
        "rom_entry": "hk-303.program", "melody_entry": "hk-303.melody",
        "cpu": b"SM511__\x00", "sig": b"w_dkhock", "flags": 0x52,
        "kb": [0x00000000, 0x00000010, 0x00000000, 0x00000208, 0x00000000, 0x00000104, 0xA0802040, 0, 0, 0],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_dkhockey.svg", 3951, 1191, lambda ry: 56 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "dkong3": {
        "rom_zip": "shrinker/input/roms/gnw_dkong3.zip", "art_zip": "shrinker/input/artwork/gnw_dkong3.zip",
        "rom_entry": "ak-302.program", "melody_entry": "ak-302.melody",
        "cpu": b"SM511__\x00", "sig": b"w_dkong3", "flags": 0x52,
        "kb": [0x00000000, 0x00000010, 0x00000000, 0x00000208, 0x00000000, 0x00000104, 0xA0802040, 0, 0, 0],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511
        "screens": [
            ("main", "gnw_dkong3.svg", 3934, 1154, lambda ry: 56 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
        },
    "smb": {
        "rom_zip": "shrinker/input/roms/gnw_smb.zip", "art_zip": "shrinker/input/artwork/gnw_smb.zip",
        "rom_entry": "ym-801.program", "melody_entry": "ym-801.melody",
        "cpu": b"SM511__\x00", "sig": b"w_smb___", "flags": 0x52,
        "kb": [0x00A08040, 0x01080402, 0x00000010, 0, 0, 0, 0, 0, 0, 0],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM511 (same layout A/B/C+bs)
        "screens": [
            ("main", "gnw_smb.svg", 4017, 2454, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "BackgroundNS.png",
    },
    "ssparky": {
        "rom_zip": "shrinker/input/roms/gnw_ssparky.zip", "art_zip": "shrinker/input/artwork/gnw_ssparky.zip",
        "rom_entry": "bu-201",
        "cpu": b"SM510__\x00", "sig": b"w_sspark", "flags": 0x52,
        "kb": [0x00100401, 0xA0802040, 0, 0, 0, 0, 0, 0, 0, 0],
        "slot": lambda a, b, c: 64 * a + 4 * b + c,   # SM510
        "screens": [
            ("main", "gnw_ssparky.svg", 2322, 4002, lambda ry: 13 + ry),
        ],
        "bg_kind": "single", "bg_top": None, "bg_bottom": "Background.png",
        "bg_view": {
            "w": 256, "h": 165,
            "mame": [1069, 1761],
            "reflector_top": 28,  # top grey reflector strip (0-27)
            "bands": {"axis": 1, "limits": [28, 44, 69, 95, 165]},  # strips by row
            "layers": [
                ["Background.png", [0, 0, 256, 165], None, 1.0],
                ["Subtract.png", [0, 0, 256, 165], "multiply", 1.0],
                ["Overlay.png", [0, 0, 256, 165], "add", 1.0],
                ["Lines.png", [0, 0, 256, 165], None, 1.0],
                ["Frame2.png", [0, 0, 256, 165], None, 1.0],
            ]
        },
        },

}


# ---------------------------------------------------------------------------
# LCD segment rendering with Inkscape
# ---------------------------------------------------------------------------
GRAPHIC_TAGS = ('path', 'polygon', 'rect', 'ellipse', 'line', 'circle',
                'polyline', 'use')


def register_ns():
    ET.register_namespace('svg', 'http://www.w3.org/2000/svg')
    ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
    ET.register_namespace('sodipodi', 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd')


def local(el):
    tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
    return tag


def print_progress_bar(iteration, total, prefix='', suffix='', length=25):
    """Single-line progress bar (LCD-Game-Shrinker style)."""
    if total <= 0:
        return
    percent = int(100 * iteration / total)
    if percent >= 100:
        # at 100%: leave no text to the right of the bar (and clear the rest)
        suffix = ' ' * len(suffix)
    filled = int(length * iteration / total)
    bar = '=' * filled + '-' * (length - filled)
    sys.stdout.write('\r%s |%s| %3d%% %s' % (prefix, bar, percent, suffix))
    sys.stdout.flush()


def run_inkscape(args):
    if not os.path.exists(INKSCAPE):
        raise RuntimeError("Inkscape not found: %s" % INKSCAPE)
    result = subprocess.run([INKSCAPE] + args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("Inkscape fallo [rc=%d, %s]: %s" % (
            result.returncode, " ".join(str(a) for a in args)[:160],
            result.stderr[-200:]))


def find_segments(svg_path):
    """Returns {title 'x.y.z': element} for elements with <title>x.y.z</title>."""
    register_ns()
    tree = ET.parse(svg_path)
    root = tree.getroot()
    results = {}

    def walk(elem):
        title_text = None
        for child in elem:
            if local(child) == 'title' and child.text:
                m = re.match(r'^(\d+)\.(\d+)\.(\d+)$', child.text.strip())
                if m:
                    title_text = child.text.strip()
                    break
        if title_text and title_text not in results:
            results[title_text] = elem
        for child in elem:
            if local(child) in ('g', 'path'):
                walk(child)

    walk(root)
    titles = sorted(results.keys(), key=lambda t: [int(x) for x in t.split('.')])
    return results, titles


def render_single_segment(svg_path, title, container_elem, out_png, sw, sh):
    register_ns()
    tree = ET.parse(svg_path)
    root = tree.getroot()

    target_xml_ids = set()
    for sub in container_elem.iter():
        sid = sub.get('id')
        if sid:
            target_xml_ids.add(sid)

    for elem in root.iter():
        elem_id = elem.get('id')
        if local(elem) in GRAPHIC_TAGS and (elem_id not in target_xml_ids or not elem_id):
            style = elem.get('style', '')
            elem.set('style', (style + ';display:none') if style else 'display:none')

    tmp_path = out_png + ".tmp.svg"
    tree.write(tmp_path, encoding='utf-8', xml_declaration=True)
    try:
        run_inkscape(['-o', out_png, '-w', str(sw), '-h', str(sh), tmp_path])
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def segment_bbox(mask):
    xs = []
    ys = []
    for y, row in enumerate(mask):
        for x, v in enumerate(row):
            if v:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)


# ---------------------------------------------------------------------------
# LCD-Game-Shrinker method: isolated segments with export-id-only
# ---------------------------------------------------------------------------
def lay_rects(art):
    """Returns per screen (screen_x, screen_y, scr_w, scr_h,
    bg_x, bg_y, bg_w, bg_h) from the .lay (highest-priority view: No
    Reflection -> No Shadow -> Background Only). Used by the shrinker flow
    for the composite scale + moveto (replicates shrink_it.py)."""
    import xml.etree.ElementTree as ET
    lay = next((v for k, v in art.items() if k.endswith(".lay")), None)
    if not lay:
        return None
    try:
        root = ET.fromstring(lay)
    except ET.ParseError:
        return None
    view_prio = {
        "Background Only (No Reflection)": 0,
        "Backgrounds Only (No Shadow)": 1,
        "Background Only (No Shadow)": 2,
        "Background Only": 3,
    }

    def rect(el):
        b = el.find("bounds")
        if b is None:
            return None
        return (float(b.get("x")), float(b.get("y")),
                float(b.get("width")), float(b.get("height")))

    best_result = None
    best_prio = None
    for view in root.iter("view"):
        name = view.get("name")
        if name not in view_prio:
            continue
        screens = []
        elems = []
        for child in view:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "screen":
                screens.append(rect(child))
            elif tag in ("element", "overlay"):
                ref = child.get("ref") or child.get("element")
                if ref and ref not in ("Bubbles", "Blur", "Gradient",
                                       "Gradient2"):
                    elems.append((ref, rect(child)))
        if not screens or not elems:
            continue
        result = []
        for scr in screens:
            if not scr:
                continue
            scx = scr[0] + scr[2] / 2
            scy = scr[1] + scr[3] / 2
            best = None
            bestd = None
            for ref, r in elems:
                if not r:
                    continue
                cx = r[0] + r[2] / 2
                cy = r[1] + r[3] / 2
                d = (cx - scx) ** 2 + (cy - scy) ** 2
                if bestd is None or d < bestd:
                    bestd = d
                    best = r
            if best:
                result.append((scr[0], scr[1], scr[2], scr[3],
                               best[0], best[1], best[2], best[3]))
        if result and (best_prio is None or view_prio[name] < best_prio):
            best_result = result
            best_prio = view_prio[name]
    return best_result


def _rescale_svg_to_target(seg_fix, seg_target, lcd_w, lcd_h, lay_rect=None,
                           offset_y=None):
    """Rescales the SVG to the target size by creating an lcd_w x lcd_h viewBox
    and wrapping the content in a group with a scale transform (same result
    as the rescaling LCD-Game-Shrinker does with svgutils).

    fit='w'/'h' keeps the artwork aspect ratio in one dimension (like
    compose_bg with bg_fit): uniform scale by width or height, with the
    centering offset in the other dimension."""
    register_ns()
    tree = ET.parse(seg_fix)
    root = tree.getroot()
    vb = re.split(r"[ ,\t]+", root.get("viewBox", "0 0 100 100").strip())
    vw = float(vb[2])
    vh = float(vb[3])
    sx = lcd_w / vw
    sy = lcd_h / vh
    if lay_rect:
        # Shrinker composite scale: viewBox -> screen -> background canvas
        # -> LCD, with moveto (screen position on the canvas).
        scr_x, scr_y, scr_w, scr_h, bg_x, bg_y, bg_w, bg_h = lay_rect
        # contain of the canvas (real backdrop AR) + deformation of the
        # viewBox to the .lay screen (sx/sy separately): segments land
        # exactly on the artwork LCD even if their ARs differ.
        s = min(lcd_w / bg_w, H_DS / bg_h)
        sx = (scr_w / vw) * s
        sy = (scr_h / vh) * s
        tx = (scr_x - bg_x) * s + (lcd_w - bg_w * s) / 2
        if offset_y is None:
            offset_y = (H_DS - bg_h * s) / 2
        ty = (scr_y - bg_y) * s + offset_y

    for attr in ("width", "height", "viewBox", "preserveAspectRatio"):
        root.attrib.pop(attr, None)
    root.set("width", str(lcd_w))
    root.set("height", str(lcd_h))
    root.set("viewBox", "0 0 %d %d" % (lcd_w, lcd_h))

    # Wrap the visible content in a scaled group.
    content = list(root)
    g = ET.Element("{http://www.w3.org/2000/svg}g")
    if lay_rect:
        g.set("transform", "translate(%f,%f) scale(%f,%f)" % (tx, ty, sx, sy))
    else:
        g.set("transform", "scale(%f,%f)" % (sx, sy))
    for child in content:
        root.remove(child)
        g.append(child)
    root.append(g)
    tree.write(seg_target, encoding="utf-8", xml_declaration=True)
    return vw, vh


def _segment_obj_id(elem):
    """First graphical id of the element (or of its first child with an id)."""
    oid = elem.get("id")
    if not oid:
        for sub in elem.iter():
            sid = sub.get("id")
            if sid:
                oid = sid
                break
    return oid


def render_segments_shrinker(svg_path, seg_dir, sw, sh, lcd_w, lcd_h,
                             inverted, force, slot_fn=None, lay_rect=None,
                             offset_y=None):
    """Replicates the LCD-Game-Shrinker segment flow:

      1) Re-saves the SVG with Inkscape (path-name fix).
      2) Rescales the SVG to lcd_w x lcd_h (same result as the rescaling
         shrink_it.py does with svgutils).
      3) For each segment (title x.y.z) exports ONLY its object with
         'inkscape -i <id> -j' (--export-id-only), like shrink_it.py
         (L702-711): the segment ends up isolated, over a black (inverted)
         or white background with its antialias, without neighbor segments.
      4) Queries each object's coordinates with 'inkscape --query-all' on
         the already-rescaled SVG (coordinates in lcd space).
      5) For each segment, packs the 4-bit intensity from its isolated PNG
         and applies the 'oversize check & fix' (crop if it exceeds the
         limits or has negative coordinates).

    Returns (segments_by_slot, titles). Each segment is a dict with the
    binary lcd_w x lcd_h mask and the cropped bbox (x, y, w, h)."""
    register_ns()

    # 1) Segment fix: re-open/save the SVG with Inkscape to normalize the
    #    path names that Inkscape modifies when editing.
    seg_fix = os.path.join(seg_dir, "segments_fix.svg")
    md5_fix = seg_fix + ".svg_md5"
    need_fix = force or not os.path.exists(seg_fix)
    if not need_fix and os.path.exists(md5_fix):
        h = hashlib.md5(open(svg_path, "rb").read()).hexdigest()
        need_fix = open(md5_fix).read().strip() != h
    if need_fix:
        run_inkscape(["--query-all", svg_path, "--export-overwrite",
                      "--export-type=svg", "-o", seg_fix])
        with open(md5_fix, "w") as f:
            f.write(hashlib.md5(open(svg_path, "rb").read()).hexdigest())

    # 2) Rescale the SVG to the target size (like svgutils in shrink_it).
    seg_target = os.path.join(seg_dir, "segments_target.svg")
    _rescale_svg_to_target(seg_fix, seg_target, lcd_w, lcd_h, lay_rect,
                           offset_y)

    # 3) Find segments (title x.y.z) and their coordinates in lcd space
    #    (the SVG is already rescaled: --query-all reports in px of the
    #    256 x lcd_h document).
    segments, titles = find_segments(seg_fix)
    print("  %d segments in %s"
          % (len(titles), os.path.basename(seg_dir)))

    qr = subprocess.run([INKSCAPE, "--query-all", seg_target],
                        capture_output=True, text=True)
    queries = {}
    for line in qr.stdout.splitlines():
        parts = line.split(",")
        if len(parts) == 5:
            try:
                queries[parts[0]] = (float(parts[1]), float(parts[2]),
                                     float(parts[3]), float(parts[4]))
            except ValueError:
                continue

    # 4) Export each isolated segment (--export-id-only), like
    #    LCD-Game-Shrinker (shrink_it.py L702-711): 'inkscape -i <id> -j'
    #    exports ONLY that object over the black (inverted) or white
    #    background, without neighbor segments. Cache by md5 of seg_target.
    bg_hex = "#000000" if inverted else "#FFFFFF"
    iso_md5 = os.path.join(seg_dir, "segments_iso.svg_md5")
    h_tgt = hashlib.md5(open(seg_target, "rb").read()).hexdigest()
    need_iso = force
    if not need_iso and os.path.exists(iso_md5):
        need_iso = open(iso_md5).read().strip() != h_tgt
    if not need_iso:
        need_iso = any(not os.path.exists(os.path.join(seg_dir, t + ".png"))
                       for t in titles)
    if need_iso:
        # Clean up obsolete PNGs (pre-3x method or full renders).
        valid = set(t + ".png" for t in titles)
        for f in os.listdir(seg_dir):
            if f.endswith(".png") and f not in valid:
                os.remove(os.path.join(seg_dir, f))
        for i, t in enumerate(titles):
            obj_id = _segment_obj_id(segments[t])
            if not obj_id:
                print("  warning: segment %s has no exportable id" % t)
                continue
            print_progress_bar(i + 1, len(titles), prefix="  segments",
                               suffix=t)
            png_file = os.path.join(seg_dir, t + ".png")
            # Inkscape sometimes fails intermittently (rc!=0 without stderr):
            # retry a few times before aborting the build.
            for attempt in range(3):
                try:
                    run_inkscape(["-i", obj_id, "-j", "--export-area-snap",
                                  "--export-background=%s" % bg_hex,
                                  "--export-type=png",
                                  "-o", png_file, seg_target])
                    break
                except RuntimeError:
                    if attempt == 2:
                        raise
                    print("  retry %s (%d/3)" % (t, attempt + 2))
        with open(iso_md5, "w") as f:
            f.write(h_tgt)
        if titles:
            sys.stdout.write("\n")

    # 5) Pack the 4-bit intensity from each isolated PNG.
    #    In inverted the background is black (G=0 -> 0, transparent) and the
    #    segment white (G=255 -> 15); in normal the background is white (15)
    #    and the segment black (0). The binary mask is kept separately for
    #    the bbox; the intensity is packed into the .gnw (same as the
    #    LCD-Game-Emulator: SEG_TRANSPARENT_COLOR = 0 if inverted, 0xF otherwise).
    result = {}
    for i, t in enumerate(titles):
        print_progress_bar(i + 1, len(titles), prefix="  packing",
                           suffix=t)
        a, b, c = (int(v) for v in t.split("."))
        if slot_fn is None:
            slot = a * 64 + b * 4 + c      # SM510/511 default
        else:
            slot = slot_fn(a, b, c)        # cfg applies the real slot

        obj_id = _segment_obj_id(segments[t])
        q = queries.get(obj_id) if obj_id else None
        if not q:
            continue
        x = int(float(q[0]))
        y = int(float(q[1]))

        # dimensions of the isolated PNG (bbox of the exported object)
        png_file = os.path.join(seg_dir, t + ".png")
        im = Image.open(png_file).convert("RGB")
        w, h = im.size

        # oversize check & fix (same as LCD-Game-Shrinker)
        if x + w > lcd_w:
            w = lcd_w - x
        if y + h > lcd_h:
            h = lcd_h - y
        if x < 0:
            w += x
            x = 0
        if y < 0:
            h += y
            y = 0
        if w <= 0 or h <= 0:
            continue

        m = [[0] * lcd_w for _ in range(lcd_h)]
        inten = [[0xF] * lcd_w for _ in range(lcd_h)]
        spx = im.load()
        for py in range(h):
            gy = y + py
            for px in range(w):
                gx = x + px
                r, g, b = spx[px, py]
                v = g >> 4
                # Full intensity G>>4 (same as LCD-Game-Shrinker:
                # getdata(band=1) >> 4). The border antialias is kept in the
                # intensity and the emulator shows it with rgb_multiply.
                inten[gy][gx] = v
                if inverted:
                    if v > 0:          # segment pixel (white/grey)
                        m[gy][gx] = 1
                else:
                    if v < 0xF:        # segment pixel (black/antialias)
                        m[gy][gx] = 1

        # bbox = PNG rect (x, y, w, h after the oversize fix), same as the
        # LCD-Game-Shrinker (tab_x/tab_y + isolated PNG size).
        rx, ry, rw, rh = x, y, w, h
        result[slot] = {
            "mask": m,
            "intensity": inten,
            "bbox": (rx, ry, rw, rh),
            "title": t,
        }
    if titles:
        sys.stdout.write("\n")
    return result, titles


# ---------------------------------------------------------------------------
# .gnw packing (LCD-Game-Emulator format + 2 RGB565 backdrops)
# ---------------------------------------------------------------------------
def _lcd_render(game):
    """Renders the 'all segments ON' state of game's .gnw and returns the
    numpy RGB array 256x192 (single) or 256x384 (dual, stacked screens).

    - inverted (Panorama/Tabletop): backdrop x intensity (rgb_multiply)
    - normal: dim the backdrop with the intensity (pure black -> 39)
    """
    path = os.path.join(GNW_DIR, "gnw_%s.gnw" % game)
    d = open(path, "rb").read()

    def blk(i):
        return struct.unpack("<II", d[20 + 8 * i:28 + 8 * i])

    obg, bgsz = blk(0)          # topNS + bottomNS (Bmp16 NDS)
    osg, segsz = blk(1)
    oo, _ = blk(2)
    ox, _ = blk(3)
    oy, _ = blk(4)
    oh, _ = blk(5)
    ow, _ = blk(6)
    flags = struct.unpack("<I", d[16:20])[0]
    inverted = bool(flags & 0x01)
    transparent = 0 if inverted else 0xF

    top = d[obg:obg + 98304]
    bot = d[obg + 98304:obg + bgsz]
    seg = d[osg:osg + segsz]

    def bmp16_to_rgb(buf):
        arr = np.frombuffer(buf, dtype="<u2", count=256 * 192).reshape(192, 256)
        r = ((arr & 0x1F) << 3).astype(np.uint16)
        g = (((arr >> 5) & 0x1F) << 3).astype(np.uint16)
        b = (((arr >> 10) & 0x1F) << 3).astype(np.uint16)
        return np.stack([r, g, b], -1)

    # Intensity per screen: MAIN (y<192) and SUB (y>=192, mapped to y-192).
    # Backdrop assignment follows the emulator: in dual (main_uses_top=1)
    # MAIN uses topNS and SUB uses bottomNS; in single MAIN uses bottomNS.
    inten_main = np.full((192, 256), transparent, dtype=np.uint8)
    inten_sub = np.full((192, 256), transparent, dtype=np.uint8)
    for s in range(256):
        w = struct.unpack_from("<H", d, ow + 2 * s)[0]
        h = struct.unpack_from("<H", d, oh + 2 * s)[0]
        if not w or not h:
            continue
        x = struct.unpack_from("<H", d, ox + 2 * s)[0]
        y = struct.unpack_from("<H", d, oy + 2 * s)[0]
        off = struct.unpack_from("<I", d, oo + 4 * s)[0]
        for py in range(h):
            gy = y + py
            if gy >= 192:
                sy = gy - 192
                if sy < 0 or sy >= 192:
                    continue
                for px in range(w):
                    gx = x + px
                    if gx < 0 or gx >= 256:
                        continue
                    nib = off + py * w + px
                    bb = seg[nib >> 1]
                    v = (bb & 0xF) if (nib & 1) else (bb >> 4)
                    if v != transparent:
                        inten_sub[sy, gx] = (max if inverted else min)(
                            int(inten_sub[sy, gx]), v)
            else:
                if gy < 0:
                    continue
                for px in range(w):
                    gx = x + px
                    if gx < 0 or gx >= 256:
                        continue
                    nib = off + py * w + px
                    bb = seg[nib >> 1]
                    v = (bb & 0xF) if (nib & 1) else (bb >> 4)
                    if v != transparent:
                        inten_main[gy, gx] = (max if inverted else min)(
                            int(inten_main[gy, gx]), v)

    dual = bool((inten_sub != transparent).any())

    def render(bg, inten):
        cur = ((inten << 4) | inten).astype(np.uint16)[..., None]
        if inverted:
            return ((bg * cur) >> 8).astype(np.uint8)
        # normal: dim the backdrop with the intensity (like the ref. emulator);
        # pure black -> 39 (LCD-Game-Emulator) and 0xF stays transparent.
        cur = np.where(cur == 0, 39, cur)
        out = ((bg * cur) >> 8).astype(np.uint8)
        seg_on = (inten < 0xF)[..., None]
        return np.where(seg_on, out, bg).astype(np.uint8)

    if dual:
        # Multiscreen game: stack the two screens (game top above, bottom
        # below), backdrop+segments already rendered by render().
        out_main = render(bmp16_to_rgb(top), inten_main)
        out_sub = render(bmp16_to_rgb(bot), inten_sub)
        return np.vstack([out_main, out_sub])
    return render(bmp16_to_rgb(bot), inten_main)  # 256x192


def render_preview(game):
    """Saves the LCD preview (backdrop + segments, 256x192 or 256x384) to
    shrinker/preview/gnw_<game>.png."""
    out = _lcd_render(game)
    out_dir = os.path.join(ROOT, "shrinker", "preview")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "gnw_%s.png" % game)
    Image.fromarray(out).save(out_path)
    return out_path



# Case preview: _carcasa_ventana, _artwork_lcd_render, _case_screen_rect
# and render_preview_case were moved to shrinker/build_gnw_case.py.

def gw_src_dir(game):
    return os.path.join(SRC_DIR, "gnw_" + game)


def build_gw(game, force, idx=None, total=None):
    cfg = GAMES[game]
    gdir = gw_src_dir(game)
    os.makedirs(gdir, exist_ok=True)
    if idx is None or total is None:
        print("===== %s =====" % game)
    else:
        print("===== %s (%d/%d) =====" % (game, idx + 1, total))

    # 1) roms ZIP: binary ROM + segment SVGs (+ optional melody)
    with zipfile.ZipFile(os.path.join(ROOT, cfg["rom_zip"])) as z:
        rom = z.read(cfg["rom_entry"])
        svgs = {n: z.read(n) for n in z.namelist() if n.endswith(".svg")}
        melody = z.read(cfg["melody_entry"]) if cfg.get("melody_entry") else b""
    print("  ROM %s (%d bytes), %d SVGs%s" % (
        cfg["rom_entry"], len(rom), len(svgs),
        ", melody %d bytes" % len(melody) if melody else ""))

    # 2) artwork ZIP: scene PNGs + layout (to align the backdrop)
    with zipfile.ZipFile(os.path.join(ROOT, cfg["art_zip"])) as z:
        art = {n: z.read(n) for n in z.namelist()
               if n.endswith(".png") or n.endswith(".lay")}

    # 3) LCD segments per screen (Inkscape render at 3x)
    sd = bytearray()
    offs = [0] * 256; xs = [0] * 256; ys = [0] * 256
    ws = [0] * 256; hs = [0] * 256
    pixel_owners = bytearray(W * H_DS * 2)
    n = 0; nib = 0; pending = 0x0

    layr = lay_rects(art)
    # In dual, lay_rects() returns the screens in .lay order (typically
    # top, bottom), while cfg["screens"] uses (bottom, top) / (right, left):
    # they are sorted to pair them up.
    if layr and len(layr) > 1:
        names = [s[0] for s in cfg["screens"]]
        first = names[0]
        if first in ("bottom", "top"):
            layr = sorted(layr, key=lambda r: r[1],
                          reverse=(first == "bottom"))
        elif first in ("right", "left"):
            layr = sorted(layr, key=lambda r: r[0],
                          reverse=(first == "right"))
    n_scr = len(cfg["screens"])
    bg_fit = {}
    for (i, (screen_name, svg_name, sw, sh, ds_y_fn)) in enumerate(cfg["screens"]):
        lcd_w, lcd_h = 256, 165
        svg_path = os.path.join(gdir, svg_name)
        with open(svg_path, "wb") as f:
            f.write(svgs[svg_name])

        inverted = bool(cfg.get("lcd_inverted", False))

        seg_dir = os.path.join(gdir, screen_name)
        # contain per screen: uniform scale (real AR) on the physical
        # 256x192 screen.
        lrect = layr[i] if layr and i < len(layr) else None
        offset_y = None
        if lrect:
            s = min(lcd_w / lrect[6], H_DS / lrect[7])
            fw = lrect[6] * s
            fh = lrect[7] * s
            lcd_h = H_DS   # packing space = full physical screen
            fx = int(round((lcd_w - fw) / 2))
            if n_scr == 1:
                # single: backdrop centered on its physical screen
                fy = int(round((H_DS - fh) / 2))
                bg_fit["bottom"] = {"w": int(round(fw)),
                                    "h": int(round(fh)),
                                    "x": fx, "y": fy}
                ds_y_fn = lambda ry: ry
            elif "bottom" in screen_name or "right" in screen_name:
                # game bottom screen (DS bottom bitmap): the backdrop
                # starts at y=0 to touch the top screen.
                bg_fit["bottom"] = {"w": int(round(fw)),
                                    "h": int(round(fh)),
                                    "x": fx, "y": 0}
                ds_y_fn = lambda ry: H_DS + ry
                offset_y = 0
            else:
                # game top screen (DS top bitmap): ends at y=H_DS to touch
                # the bottom screen. The ry already includes the offset_y
                # (=fy), so ds_y = ry.
                fy = H_DS - int(round(fh))
                bg_fit["top"] = {"w": int(round(fw)),
                                 "h": int(round(fh)),
                                 "x": fx, "y": fy}
                ds_y_fn = lambda ry: ry
                offset_y = fy
        seg_data, titles = render_segments_shrinker(
            svg_path, seg_dir, sw, sh, lcd_w, lcd_h, inverted, force,
            cfg["slot"], lrect, offset_y)
        for slot, info in seg_data.items():
            r = info["mask"]
            inten = info.get("intensity")
            rx, ry, rw, rh = info["bbox"]
            ds_y = ds_y_fn(ry)

            offs[slot] = nib
            for yy in range(ry, ry + rh):
                for xx in range(rx, rx + rw):
                    if inten is not None:
                        v = inten[yy][xx]          # real intensity 0-15
                    else:
                        v = 0x2 if r[yy][xx] else 0xF
                    gx = xx
                    gy = ds_y + yy - ry
                    transparent = 0x0 if inverted else 0xF
                    if v != transparent and 0 <= gx < W and 0 <= gy < H_DS * 2:
                        owner_idx = gy * W + gx
                        pixel_owners[owner_idx] += 1
                        if pixel_owners[owner_idx] > 2:
                            raise ValueError(
                                "%s: more than two segments overlap at pixel (%d, %d), slot %d"
                                % (game, gx, gy, slot))
                    if nib & 1 == 0:
                        pending = v << 4
                    else:
                        sd.append(pending | v)
                    nib += 1
            xs[slot], ys[slot], ws[slot], hs[slot] = rx, ds_y, rw, rh
            n += 1
    if nib & 1:
        sd.append(pending | 0xF)
    print("  slots:", n, "bitmap:", len(sd), "nibbles:", nib)

    # 4) topNS/bottomNS backdrops: each screen stretched to its contained
    # rect (contain, from the .lay) and centered on its physical screen.
    lcd_w, lcd_h = 256, 165
    mame_dict = {}
    if layr:
        for (i, (screen_name, *_)) in enumerate(cfg["screens"]):
            if i >= len(layr):
                break
            key = "bg_top" if screen_name in ("top", "left") else "bg_bottom"
            mame_dict[key] = (int(round(layr[i][6])), int(round(layr[i][7])))
    top_nds, bot_nds = compose_bg(art, cfg["bg_top"], cfg["bg_bottom"],
                                  cfg["bg_kind"], bg_fit=bg_fit or None,
                                  lcd_h=lcd_h,
                                  reflector=(cfg.get("bg_reflector", 25) if not cfg.get("lcd_inverted") else None),
                                  mame=mame_dict or None,
                                  view=cfg.get("bg_view"))
    bg_size = len(top_nds) + len(bot_nds)

    # 5) Assemble the .gnw
    def al(v, a):
        return (v + a - 1) & ~(a - 1)

    osg = 108
    oo = al(osg + len(sd), 4)
    ox = oo + 0x400
    oy = ox + 0x200
    oh = oy + 0x200
    ow = oh + 0x200
    op = ow + 0x200
    om = op + 0x1000                      # SM511 melody (after the program)
    ok = om + len(melody)                 # keyboard table
    obg = ok + len(cfg["kb"]) * 4
    tot = obg + bg_size

    hd = bytearray(100)
    hd[0:8] = cfg["cpu"]
    hd[8:16] = cfg["sig"]
    flags = cfg["flags"] | (0x01 if cfg.get("lcd_inverted", False) else 0)
    struct.pack_into("<I", hd, 16, flags)
    for i, (_, o, s) in enumerate([
        ("bg", obg, bg_size), ("seg", osg, len(sd)), ("off", oo, 0x400),
        ("x", ox, 0x200), ("y", oy, 0x200), ("h", oh, 0x200), ("w", ow, 0x200),
        ("mel", om, len(melody)), ("prog", op, 0x1000), ("kb", ok, len(cfg["kb"]) * 4)]):
        struct.pack_into("<I", hd, 20 + 8 * i, o)
        struct.pack_into("<I", hd, 24 + 8 * i, s)

    g = bytearray(tot)
    g[0:100] = hd
    g[osg:osg + len(sd)] = sd
    for i in range(256):
        struct.pack_into("<I", g, oo + 4 * i, offs[i])
        struct.pack_into("<H", g, ox + 2 * i, xs[i])
        struct.pack_into("<H", g, oy + 2 * i, ys[i])
        struct.pack_into("<H", g, oh + 2 * i, hs[i])
        struct.pack_into("<H", g, ow + 2 * i, ws[i])
    g[op:op + len(rom)] = rom
    if melody:
        g[om:om + len(melody)] = melody
    for i, k in enumerate(cfg["kb"]):
        struct.pack_into("<I", g, ok + 4 * i, k)
    g[obg:obg + bg_size] = top_nds + bot_nds

    os.makedirs(GNW_DIR, exist_ok=True)
    out = os.path.join(GNW_DIR, "gnw_%s.gnw" % game)
    with open(out, "wb") as f:
        f.write(g)
    print("  GW:", out, "(%d bytes)" % len(g))
    print("  preview:", render_preview(game))


def main():
    force = False
    targets = []
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--force":
            force = True
        elif a == "--only":
            i += 1
            targets.append(args[i])
        elif a.startswith("--only="):
            targets.append(a.split("=", 1)[1])
        else:
            targets.append(a)          # game(s) as positional arguments
        i += 1

    # Available games = those having their .zip in roms/ and artwork/
    def _disponible(g):
        cfg = GAMES[g]
        return (os.path.exists(os.path.join(ROOT, cfg["rom_zip"])) and
                os.path.exists(os.path.join(ROOT, cfg["art_zip"])))

    games = sorted(g for g in GAMES if _disponible(g))
    todo = targets if targets else games
    valid = [g for g in todo if g in GAMES]
    if not valid:
        print("unknown game(s): %s (valid: %s)" % (todo, ", ".join(games)))
        sys.exit(1)

    for i, g in enumerate(valid):
        build_gw(g, force, i, len(valid))
    print("\nOK")


if __name__ == "__main__":
    main()


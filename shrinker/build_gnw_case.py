#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Builds the CASE previews of the Game & Watch games: composites the case
artwork (PNG from the artwork ZIP) with the LCD (backdrop + segments) pasted
into its window/hole and saves it to shrinker/output/gnw/case/gnw_<game>_case.png
(256x192), stretching the case according to its orientation, along with the
Bmp16 binary gnw/gnw_<game>.case loaded by the DS menu.

It is independent of shrink_gnw.py: it reuses its GAMES, ROOT, GNW_DIR and the
geometry/render functions (lay_rects, _lcd_render, flatten_alpha,
run_inkscape, gw_src_dir) via import. The backdrop+segment previews stay in
shrink_gnw.py (render_preview).

Usage:
    python shrinker/build_gnw_case.py                 # all case previews
    python shrinker/build_gnw_case.py --only pchute   # a single game
"""
import io
import os
import sys
import time
import zipfile

import numpy as np
import xml.etree.ElementTree as ET
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shrink_gnw import (
    GAMES, ROOT, GNW_DIR, lay_rects, _lcd_render,
    flatten_alpha, run_inkscape, gw_src_dir, print_progress_bar,
)

# designated cases: always used for those games (window detection ignored).
# mariocmt/helmet have no hole; boxing/dkhockey/dkong3 use Unit.png to make
# the artwork uniform.
CASE_OVERRIDE = {
    "mariocmt": "Unit-Only.png", "helmet": "CN-07.png",
    "boxing": "Unit.png", "dkhockey": "Unit.png", "dkong3": "Unit.png",
}
# games whose glass core IS the display (they look fine using the hole).
# None for now: all the overflowing ones use the .lay area (sr) to avoid
# the black frame of the semi-transparent zone around the core.
# The (empty) set is kept in case some game prefers the core later on.
CASE_FORCE_HOLE = set()


def _carcasa_ventana(im):
    """Returns the list of transparent inner windows (LCD holes) as bbox
    (x, y, w, h) sorted by position. A vertical dual (DK) has two stacked
    rects; a horizontal dual (Mario) two side by side.
    Note: they are the large connected components not touching the border."""
    arr = np.array(im.convert("RGBA"))
    H, W = arr.shape[:2]
    alpha = (arr[:, :, 3] == 0).astype(np.uint8)
    seen = np.zeros_like(alpha, dtype=bool)
    wins = []
    for y in range(H):
        for x in range(W):
            if not alpha[y, x] or seen[y, x]:
                continue
            pts = []
            stack = [(y, x)]
            seen[y, x] = True
            while stack:
                cy, cx = stack.pop()
                pts.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx),
                               (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < H and 0 <= nx < W and alpha[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(pts) < 500:
                continue
            ys = [p[0] for p in pts]
            xs = [p[1] for p in pts]
            if min(ys) == 0 or min(xs) == 0 or max(ys) == H - 1 or max(xs) == W - 1:
                continue
            wins.append((min(xs), min(ys), max(xs) - min(xs) + 1,
                         max(ys) - min(ys) + 1))
    # sort: landscape -> by x (side by side); vertical -> by y (stacked)
    wins.sort(key=lambda b: (b[1], b[0]) if (im.size[1] >= im.size[0]) else (b[0], b[1]))
    return wins


def _artwork_lcd_render(game, idx=None, total=None):
    """Composites the LCD directly from the artwork using the 'Background Only
    (No Shadow)' view: the canvas is the Background element (bg_w x bg_h),
    the backdrop is the layers stretched to that canvas, and the SVG
    segments are rendered at screen size and positioned with their offset
    relative to the backdrop. In dual, screens are stacked (bg_top above,
    bg_bottom below). Returns a PIL RGB image, or None if not."""
    cfg = GAMES[game]
    with zipfile.ZipFile(os.path.join(ROOT, cfg["art_zip"])) as z:
        art = {n: z.read(n) for n in z.namelist()
               if n.endswith(".png") or n.endswith(".lay")}
    layr = lay_rects(art)
    if not layr:
        return None
    names = [s[0] for s in cfg["screens"]]
    if len(layr) > 1:
        first = names[0]
        if first in ("bottom", "top"):
            layr = sorted(layr, key=lambda r: r[1], reverse=(first == "bottom"))
        elif first in ("right", "left"):
            layr = sorted(layr, key=lambda r: r[0], reverse=(first == "right"))
    with zipfile.ZipFile(os.path.join(ROOT, cfg["rom_zip"])) as z:
        svgs = {n: z.read(n) for n in z.namelist() if n.endswith(".svg")}

    # Per-game progress bar: per screen, the backdrop layers + 1 for the
    # segment render (excluding the global game counter).
    def _layers(screen_name):
        laylist = cfg["bg_top"] if (screen_name in ("top", "left")) else cfg["bg_bottom"]
        return laylist if isinstance(laylist, list) else [laylist]
    total_units = sum(len(_layers(s)) + 1 for (s, _, _, _, _) in cfg["screens"])
    done = [0]

    def tick(tag):
        done[0] += 1
        gcnt = (" [%2d/%d]" % (idx, total)) if (idx and total) else ""
        print_progress_bar(done[0], total_units,
                           prefix="  case %-12s%s" % (game, gcnt),
                           suffix=str(tag).ljust(32))

    def build_tile(screen_name, svg_name, sr):
        scr_x, scr_y, scr_w, scr_h, bg_x, bg_y, bg_w, bg_h = sr
        cw = max(1, int(round(bg_w)))
        ch = max(1, int(round(bg_h)))
        laylist = cfg["bg_top"] if (screen_name in ("top", "left")) else cfg["bg_bottom"]
        layers = laylist if isinstance(laylist, list) else [laylist]
        comp = None
        for k, png in enumerate(layers):
            im = flatten_alpha(art, png) if k == 0 else \
                Image.open(io.BytesIO(art[png])).convert("RGBA")
            im = im.resize((cw, ch), Image.LANCZOS)
            if comp is None:
                comp = im.convert("RGB")
            else:
                comp = Image.alpha_composite(
                    comp.convert("RGBA"), im.convert("RGBA")).convert("RGB")
            tick(png)
        # segments at screen size, positioned with the offset to the backdrop
        seg_w = max(1, int(round(scr_w)))
        seg_h = max(1, int(round(scr_h)))
        tmp_seg = os.path.join(gw_src_dir(game), "_artwork_seg.svg")
        os.makedirs(gw_src_dir(game), exist_ok=True)
        with open(tmp_seg, "wb") as f:
            f.write(svgs[svg_name])
        tmp_png = os.path.join(gw_src_dir(game), "_artwork_seg.png")
        run_inkscape(["-o", tmp_png, "-w", str(seg_w), "-h", str(seg_h), tmp_seg])
        tick("segments")
        seg = Image.open(tmp_png).convert("RGBA")
        seg_arr = np.array(seg)
        dark = seg_arr[:, :, :3].mean(axis=2) < 200
        seg_alpha = np.zeros((seg_arr.shape[0], seg_arr.shape[1], 4), dtype=np.uint8)
        seg_alpha[:, :, 3] = dark.astype(np.uint8) * 255
        seg_img = Image.fromarray(seg_alpha)
        # position: real offset of the screen within the backdrop (pillow
        # crops whatever falls outside the canvas, e.g. negative offset in ball).
        px = int(round(scr_x - bg_x))
        py = int(round(scr_y - bg_y))
        comp.paste(seg_img, (px, py), seg_img)
        return comp

    top = []
    bottom = []
    for i, (screen_name, svg_name, sw, sh, fn) in enumerate(cfg["screens"]):
        tile = build_tile(screen_name, svg_name, layr[i])
        (top if screen_name in ("top", "left") else bottom).append(tile)
    tiles = top + bottom
    if not tiles:
        return None
    if len(tiles) == 1:
        return tiles[0]
    total_h = sum(t.size[1] for t in tiles)
    out = Image.new("RGB", (tiles[0].size[0], total_h))
    y = 0
    for tile in tiles:
        out.paste(tile, (0, y))
        y += tile.size[1]
    return out


def _case_screen_rect(game, case_png):
    """Computes (x, y, w, h) of the .lay screen area within the case PNG
    (case_png = file name), using the .lay view where case and screen
    coexist. None if not possible."""
    cfg = GAMES[game]
    with zipfile.ZipFile(os.path.join(ROOT, cfg["art_zip"])) as z:
        lay = next((z.read(n) for n in z.namelist() if n.endswith(".lay")), None)
        png = z.read(case_png)
    if lay is None:
        return None
    case_pil = Image.open(io.BytesIO(png)).convert("RGBA")
    pw, ph = case_pil.size
    root = ET.fromstring(lay)

    def rect(el):
        b = el.find("bounds")
        if b is None:
            return None
        return tuple(float(b.get(k)) for k in ("x", "y", "width", "height"))

    modelo = cfg["rom_entry"].split(".")[0].split("_")[0].lower()
    case_prefix = case_png[:-4].lower()
    for v in root.iter("view"):
        elems = {}
        scr = None
        bg_rect = None
        for c in v:
            tag = c.tag.rsplit("}", 1)[-1]
            if tag == "screen":
                scr = rect(c)
            elif tag in ("element", "overlay"):
                ref = (c.get("ref") or "").lower()
                r = rect(c)
                if r is None:
                    continue
                elems[ref] = r
                # the LCD area is the Background element (the artwork); the
                # screen can be ~a few px above (shifted).
                if ref == "background" or ref.endswith("background"):
                    bg_rect = r
        # the LCD area = Background if present, otherwise the screen
        scr = bg_rect or scr
        if scr is None:
            continue
        # case: the element whose ref matches the case PNG
        case_rect = elems.get(case_prefix) or elems.get(modelo)
        if case_rect is None:
            continue
        # approx viewport = bbox of all elements
        xs = [r[0] for r in elems.values()] + [r[0] + r[2] for r in elems.values()]
        ys = [r[1] for r in elems.values()] + [r[1] + r[3] for r in elems.values()]
        vp = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        # case PNG size
        cx, cy, cw, ch = case_rect
        sx, sy, sw, sh = scr
        # screen position relative to the case (scaled to the PNG)
        x = (sx - cx) / cw * pw
        y = (sy - cy) / ch * ph
        w = sw / cw * pw
        h = sh / ch * ph
        if w <= 0 or h <= 0:
            continue
        return (int(round(x)), int(round(y)), int(round(w)), int(round(h)))
    return None


def render_preview_case(game, idx=None, total=None):
    """Composites the Game & Watch case (artwork PNG) with the LCD (backdrop
    + segments) pasted into its window(s), and saves it on a 256x192 canvas
    stretching the case according to its orientation (fills the width on
    landscape ones, the height on vertical ones), keeping the aspect ratio
    and with white strips on whatever is left."""
    cfg = GAMES[game]
    with zipfile.ZipFile(os.path.join(ROOT, cfg["art_zip"])) as z:
        art = {n: z.read(n) for n in z.namelist() if n.endswith(".png")}
        # display rects (screen within the backdrop) to crop the LCD
        _layr = lay_rects({n: z.read(n) for n in z.namelist()
                           if n.endswith(".lay")})

    # Background color for the final canvas: flat white, so the strips left
    # by the "contain" fit are white.
    bg = (255, 255, 255)

    # Case = PNG with an inner window (LCD hole). Unit* and the model name
    # (the real case) are prioritized; the other PNGs are only a fallback
    # when neither has a window. Chosen by largest window area. Backdrop is
    # ignored (it is the backdrop, not the case).
    modelo = cfg["rom_entry"].split(".")[0].split("_")[0]
    pri = [n for n in art if n.startswith("Unit")]
    pri += [n for n in art if n[:-4].lower() == modelo.lower()]
    pri = list(dict.fromkeys(pri))
    resto = [n for n in sorted(art) if "/" not in n
             and not n.startswith("Backdrop") and n not in pri]
    best = None
    best_area = 0
    case = None

    def _cand_max(cands):
        b, ba, cim = None, 0, None
        for n in cands:
            try:
                im = Image.open(io.BytesIO(art[n])).convert("RGBA")
            except Exception:
                continue
            if im.size[0] * im.size[1] <= 0:
                continue
            wins = _carcasa_ventana(im)
            if wins:
                a = max((w[2] * w[3]) for w in wins)
                if a > ba:
                    ba, b, cim = a, n, im
        return b, ba, cim

    best, best_area, case = _cand_max(pri)
    if best is None:
        best, best_area, case = _cand_max(resto)
    # designated case: it always wins if present in the artwork
    fc = CASE_OVERRIDE.get(game)
    if fc is not None and fc in art:
        best = fc
        case = Image.open(io.BytesIO(art[fc])).convert("RGBA")
    if best is None:
        return None

    lcd = _artwork_lcd_render(game, idx, total)
    if lcd is None:
        lcd = Image.fromarray(_lcd_render(game)).convert("RGB")  # fallback .gnw
    lcd = lcd.convert("RGB")  # LCD at the .lay high resolution (or 256x192)
    n_scr = len(cfg["screens"])
    sr = _case_screen_rect(game, best)
    holes = _carcasa_ventana(case) or []
    usar_contain = False
    if n_scr == 1:
        if sr is not None and holes:
            # artwork hole = glass core. If the .lay sr overflows that core
            # (similar area, small ratio) there are two possibilities:
            #   - games where the core IS the display (boxing/dkhockey/dkong3):
            #     use the hole (core).
            #   - the rest: the sr is the real display and the core leaves the
            #     semi-transparent zone around visible (black frame) -> use sr.
            hole = max(holes, key=lambda w: w[2] * w[3])
            ratio = (sr[2] * sr[3]) / float(hole[2] * hole[3])
            overflows = (sr[0] < hole[0] or sr[1] < hole[1] or
                        sr[0] + sr[2] > hole[0] + hole[2] or
                        sr[1] + sr[3] > hole[1] + hole[3])
            if overflows and ratio < 2.5:
                wins = [hole if game in CASE_FORCE_HOLE else sr]
                usar_contain = True
            else:
                wins = [sr]
        elif sr is not None:
            wins = [sr]
        else:
            wins = sorted(holes, key=lambda w: w[2] * w[3], reverse=True)[:n_scr]
            usar_contain = True
    else:
        wins = sorted(holes, key=lambda w: w[2] * w[3], reverse=True)[:n_scr]
    if not wins:
        return None
    case_vertical = case.size[1] >= case.size[0]
    wins.sort(key=lambda b: (b[1], b[0]) if case_vertical else (b[0], b[1]))
    lcd_cw = lcd.size[0]
    lcd_ch = lcd.size[1]
    n_win = len(wins)
    # "contain" (uniform scale + centering, no distortion) so the LCD does
    # not overflow or get distorted in the window; the leftover is filled
    # with the mean color of the cropped display (not the black border
    # frame). The tile is cropped to the display area (the .lay screen
    # within the canvas) to remove margin.
    for i, (vx, vy, vw, vh) in enumerate(wins):
        if n_win <= 1:
            tile = lcd
        elif lcd_ch and lcd_ch % n_win == 0:         # stacked -> vertical halves
            y0 = (lcd_ch // n_win) * i
            tile = lcd.crop((0, y0, lcd_cw, y0 + lcd_ch // n_win))
        else:                                          # side by side -> horizontal halves
            x0 = (lcd_cw // n_win) * i
            tile = lcd.crop((x0, 0, x0 + lcd_cw // n_win, lcd_ch))
        if not usar_contain:
            tile = tile.resize((vw, vh), Image.LANCZOS)
            case.paste(tile, (vx, vy))
            continue
        # crop to the display area (the .lay screen within the canvas),
        # removing the frame/margin of the artwork around the LCD
        if n_win <= 1 and _layr and i < len(_layr):
            scr_x, scr_y, scr_w, scr_h, bg_x, bg_y, bg_w, bg_h = _layr[i]
            dx = max(0, scr_x - bg_x)
            dy = max(0, scr_y - bg_y)
            dw = min(scr_w, bg_w - dx)
            dh = min(scr_h, bg_h - dy)
            if dw > 0 and dh > 0 and (dw < tile.size[0] or dh < tile.size[1]):
                tile = tile.crop((int(dx), int(dy),
                                  int(dx + dw), int(dy + dh)))
        # stretch to fill the hole completely (no side strips): the display
        # is already cropped, it adapts to the hole width/height.
        tile = tile.resize((vw, vh), Image.LANCZOS)
        case.paste(tile, (vx, vy))

    case_rgb = case.convert("RGB")
    # Contain keeping the AR: the long axis fills its dimension (vertical
    # -> height 192 with side strips; landscape -> width 256 with strips
    # above/below).
    scale = min(256 / case_rgb.size[0], 192 / case_rgb.size[1])
    nw = max(1, int(round(case_rgb.size[0] * scale)))
    nh = max(1, int(round(case_rgb.size[1] * scale)))
    case_fit = case_rgb.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (256, 192), bg)
    canvas.paste(case_fit, ((256 - nw) // 2, (192 - nh) // 2))

    # preview in PNG (256x192) for the menu, in gnw/case/: the build_ds
    # script syncs it to /gnw/case/ on the SD card, where the menu decodes
    # it with stb_image (replacing the .gnw extension by .png).
    out_dir = os.path.join(GNW_DIR, "case")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "gnw_%s.png" % game)
    for attempt in range(4):
        try:
            canvas.save(out_path)
            break
        except OSError:
            if attempt == 3:
                raise
            time.sleep(1.0)
    return out_path


def main():
    only = None
    for a in sys.argv[1:]:
        if a == "--only":
            only = sys.argv[sys.argv.index(a) + 1]
        elif a.startswith("--only="):
            only = a.split("=", 1)[1]
    if only and only not in GAMES:
        print("unknown game: %s (valid: %s)" % (only, ", ".join(GAMES)))
        sys.exit(1)

    # Available games = those having their .zip in roms/ and artwork/
    def _disponible(g):
        cfg = GAMES[g]
        return (os.path.exists(os.path.join(ROOT, cfg["rom_zip"])) and
                os.path.exists(os.path.join(ROOT, cfg["art_zip"])))

    games = sorted(g for g in GAMES if _disponible(g))
    if only:
        render_preview_case(only)          # with --only no game counter is shown
        print()
    else:
        total = len(games)
        for i, g in enumerate(games):
            render_preview_case(g, idx=i + 1, total=total)
            print()
    print("\nOK")


if __name__ == "__main__":
    main()



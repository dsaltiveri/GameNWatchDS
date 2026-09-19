# GameNWatchDS — Game & Watch emulator for Nintendo DS

Homebrew emulator for the Nintendo DS that brings together Game & Watch games
in a single ROM, selectable from a main menu:

| Game                               | Model     | CPU      | Screens | File                   |
| ---------------------------------- | --------- | -------- | ------- | ---------------------- |
| Ball                               | AC-01     | SM5A     | 1       | gnw_ball.gnw            |
| Balloon Fight                      | BF-107    | SM511    | 1       | gnw_bfightn.gnw         |
| Balloon Fight (Crystal Screen)     | BF-803    | SM511    | 1       | gnw_bfight.gnw          |
| Black Jack                         | BJ-60     | SM512    | 2       | gnw_bjack.gnw           |
| Bomb Sweeper                       | BD-62     | SM512    | 2       | gnw_bsweep.gnw          |
| Boxing                             | BX-301    | SM511    | 1       | gnw_boxing.gnw          |
| Chef                               | FP-24     | SM5A     | 1       | gnw_chef.gnw            |
| Climber                            | DR-106    | SM511    | 1       | gnw_climbern.gnw        |
| Climber (Crystal Screen)           | DR-802    | SM511    | 1       | gnw_climber.gnw         |
| Crab Grab                          | UD-202    | SM510    | 1       | gnw_cgrab.gnw           |
| Donkey Kong Hockey                 | HK-303    | SM511    | 1       | gnw_dkhockey.gnw        |
| Donkey Kong Jr.                    | DJ-101    | SM510    | 1       | gnw_dkjr.gnw            |
| Donkey Kong Jr. (Panorama)         | CJ-93     | SM511    | 1       | gnw_dkjrp.gnw           |
| Donkey Kong                        | DK-52     | SM510    | 2       | gnw_dkong.gnw           |
| Donkey Kong 3                      | AK-302    | SM511    | 1       | gnw_dkong3.gnw          |
| Donkey Kong Circus                 | MK-96     | SM511    | 1       | gnw_dkcirc.gnw          |
| Donkey Kong II                     | JR-55     | SM510    | 2       | gnw_dkong2.gnw          |
| Egg                                | MC-25     | SM5A     | 1       | gnw_egg.gnw             |
| Fire                               | FR-27     | SM5A     | 1       | gnw_fire.gnw            |
| Fire (Silver)                      | RC-04     | SM5A     | 1       | gnw_fires.gnw           |
| Fire Attack                        | ID-29     | SM510    | 1       | gnw_fireatk.gnw         |
| Flagman                            | FL-02     | SM5A     | 1       | gnw_flagman.gnw         |
| Gold Cliff                         | MV-64     | SM512    | 2       | gnw_gcliff.gnw          |
| Green House                        | GH-54     | SM510    | 2       | gnw_ghouse.gnw          |
| Helmet                             | CN-07     | SM5A     | 1       | gnw_helmet.gnw          |
| Judge                              | IP-05     | SM5A     | 1       | gnw_judge.gnw           |
| Lifeboat                           | TC-58     | SM510    | 2       | gnw_lboat.gnw           |
| Lion                               | LN-08     | SM5A     | 1       | gnw_lion.gnw            |
| Manhole                            | NH-103    | SM510    | 1       | gnw_manhole.gnw         |
| Manhole (Gold)                     | MH-06     | SM5A     | 1       | gnw_manholeg.gnw        |
| Mario Bros.                        | MW-56     | SM510    | 2       | gnw_mario.gnw           |
| Mario Cement Factory               | ML-102    | SM510    | 1       | gnw_mariocm.gnw         |
| Mario Cement Factory (Tabletop)    | CM-72     | SM511    | 1       | gnw_mariocmt.gnw        |
| Mario the Juggler                  | MB-108    | SM511    | 1       | gnw_mariotj.gnw         |
| Mario's Bombs Away                 | TB-94     | SM511    | 1       | gnw_mbaway.gnw          |
| Mickey & Donald                    | DM-53     | SM510    | 2       | gnw_mickdon.gnw         |
| Mickey Mouse                       | MC-25     | SM5A     | 1       | gnw_mmouse.gnw          |
| Mickey Mouse (Panorama)            | DC-95     | SM511    | 1       | gnw_mmousep.gnw         |
| Octopus                            | OC-22     | SM5A     | 1       | gnw_octopus.gnw         |
| Oil Panic                          | OP-51     | SM510    | 2       | gnw_opanic.gnw          |
| Parachute                          | PR-21     | SM5A     | 1       | gnw_pchute.gnw          |
| Pinball                            | PB-59     | SM511    | 2       | gnw_pinball.gnw         |
| Popeye                             | PP-23     | SM5A     | 1       | gnw_popeye.gnw          |
| Popeye (Panorama)                  | PG-92     | SM511    | 1       | gnw_popeyep.gnw         |
| Rain Shower                        | LP-57     | SM510    | 2       | gnw_rshower.gnw         |
| Safe Buster                        | JB-63     | SM511    | 2       | gnw_sbuster.gnw         |
| Snoopy (Panorama)                  | SM-91     | SM511    | 1       | gnw_snoopyp.gnw         |
| Snoopy Tennis                      | SP-30     | SM510    | 1       | gnw_stennis.gnw         |
| Squish                             | MG-61     | SM510    | 2       | gnw_squish.gnw          |
| Super Mario Bros.                  | YM-105    | SM511    | 1       | gnw_smbn.gnw            |
| Super Mario Bros. (Crystal Screen) | YM-801    | SM511    | 1       | gnw_smb.gnw             |
| Super Sparky                       | BU-201    | SM510    | 1       | gnw_ssparky.gnw         |
| Tropical Fish                      | TF-104    | SM510    | 1       | gnw_tfish.gnw           |
| Turtle Bridge                      | TL-28     | SM510    | 1       | gnw_tbridge.gnw         |
| Vermin                             | MT-03     | SM5A     | 1       | gnw_vermin.gnw          |
| Zelda                              | ZL-65     | SM512    | 2       | gnw_zelda.gnw           |

Based on the handheld G&W emulators by [bzhxx](https://github.com/bzhxx).
Supports games with SM500, SM5A, SM510, SM511 and SM512 CPUs (the SM511/512
include their melody).

**Nothing is embedded in the `.nds`**: each game is a self-contained `.gnw`
file (SM5xx program + LCD geometry + keyboard table + the TWO RGB565 backdrops)
read from the SD card in the `/gnw/` folder. The `.nds` weighs only ~150 KB.

## Project structure

```
GameNWatchDS/
├── Makefile / Makefile.arm9 / Makefile.arm7   # Build with BlocksDS
├── build_ds.py                                # Compiles, syncs the .gnw and launches melonDS
├── shrinker/output/gnw/                          # Generated .gnw + cache (NOT versioned)
├── arm7/source/main.c                         # ARM7 core (standard services)
├── arm9/source/
│   ├── main.c                                 # Main menu + launcher
│   ├── menu.c/h                               # Game selection (auto-scan of /gnw/)
│   ├── emulator.c/h                           # Unified common core
│   ├── games.h / games.c                      # Game catalog
│   ├── games/game_*.c                         # Per-game config (keys, tate...)
│   ├── gw_sys/                                # Game&Watch layer (shared)
│   └── cpus/                                  # SM5xx cores (shared)
├── shrinker/input/artwork/               # Original ZIPs (NOT versioned)
├── shrinker/input/roms/                  # ZIPs with ROM+SVGs (NOT versioned)
└── shrinker/shrink_gnw.py                          # Single script: generates the .gnw
```

`shrinker/input/artwork/` and `shrinker/input/roms/` hold the original ZIPs (`gnw_<game>.zip`) and are **not
versioned** (they are the local source used to regenerate the `.gnw`). The whole
emulator and its data are generated from them with `shrinker/shrink_gnw.py`.

### On the SD card (Nintendo DSi / flashcart)

```
/gnw/
├── gnw_ball.gnw       (Ball)
├── gnw_dkong.gnw      (Donkey Kong)
├── gnw_fire.gnw       (Fire)
├── gnw_smbn.gnw       (Super Mario Bros.)
└── ... (one .gnw per game, named after its ZIP)
```

Each `.gnw` is self-contained. The `background_pixel` header field stores the
two RGB565 backdrops concatenated (`topNS` + `bottomNS`, 98304 B each).
`gw_romloader_load_file()` reads the file, `gw_romloader_load()` validates it
and `gw_rom_backdrop(i)` exposes the backdrops to the renderer.

### Common code (unified)

- `arm9/source/emulator.c` — main loop, audio pacing from the TIMER0+TIMER1
  cycle odometer, direct 16bpp BG3 LCD rendering in dirty 64x64 regions,
  pixel→segment→region map building, and video/VRAM setup. It is parameterized
  with `game_desc_t` (`emulator.h`).
- `arm9/source/gw_sys/` — G&W system, segment state computation (SM510/511 and
  SM5A), and ROM loader from the SD card (`gw_romloader_load_file` +
  `gw_rom_backdrop`).
- `arm9/source/cpus/` — SM500/SM510/SM511/SM5A cores.
- `arm7/source/main.c` — standard libnds ARM7 core.

### Per-game code

Each `games/game_<name>.c` describes one specific game (keys per MAME
`hh_sm510.cpp`, screens and rendering). Examples:

- **game_dkong2.c** — D-pad + A = JUMP.
- **game_fire.c** — one screen (MAIN), SM5A rendering, keys A/→=RIGHT, Y/←=LEFT.
- **game_lboat.c** — dual-screen layout, keys A/→=RIGHT, Y/←=LEFT.
- **game_smbn.c** — SM511 CPU with melody.

## Build

Requirements: [BlocksDS](https://blocksds.skylyrac.net/) (with the
`arm-none-eabi` GCC toolchain from [Wonderful](https://wonderful.asie.pl/),
MSYS2), Python with Pillow and **Inkscape** (to render the segment SVGs).

```bash
# 1) Generate the self-contained .gnw files from the shrinker/input/artwork/ and shrinker/input/roms/ ZIPs
python shrinker/shrink_gnw.py              # all games (the 1st build renders with
                                      # Inkscape and takes a few minutes)
python shrinker/shrink_gnw.py --only fire  # a single game
python shrinker/shrink_gnw.py --force      # re-render segments (no cache)

# 2) Compile the .nds (~150 KB, no embedded ROMs)
make                     # generates GameNWatchDS.nds
make COMPDB=1            # also generates compile_commands.json (clangd)
python build_ds.py       # incremental build, syncs assets and opens melonDS
python build_ds.py --rebuild --no-launch  # clean rebuild without opening melonDS
python build_ds.py --sync-only             # only refresh the virtual SD
```

`build_ds.py` is an optional Windows/melonDS development helper; the Makefiles
remain the canonical build interface. Use `--help` for all options. The paths
to `make`, melonDS and its virtual SD can be changed with command-line options
or the `GNWDS_MAKE`, `GNWDS_MELONDS` and `GNWDS_SD_DIR` environment variables.

The `.gnw` files are generated in `shrinker/output/gnw/` (segment cache in
`shrinker/build/`; that folder is not versioned). The menu auto-scans
`/gnw/` and only lists games whose `.gnw` is
present on the SD card, so a missing `.gnw` simply means the game does not appear
in the list.

> **melonDS** (PC testing only): enable the SD card in its settings
> (Config → Firmware Settings → SD card) pointing to `C:\melonDS\SD`.
> `build_ds.py` copies the regenerated `.gnw` there automatically so that
> `fopen("/gnw/...")` finds them.

## Usage on a flashcart (real Nintendo DS)

The emulator is a standard libnds homebrew and runs on any flashcart that
executes `.nds` (R4, Acekard 2/i, DSTT, GoldR, M3, ...) with the SD in
**FAT16/32** and its **DLDI** driver. Nothing special is required.

On the root of the SD card:

```
GameNWatchDS.nds   # launched from the flashcart menu
gnw/
├── gnw_ball.gnw       # .gnw = gameplay (if missing, the game does not appear in the menu)
├── case/gnw_ball.png  # case preview (menu top screen)
├── gnw_chef.gnw
├── case/gnw_chef.png
└── ...
```

- **`.gnw`** — game data (SM5xx program + geometry + keyboard + backdrops).
  The menu **auto-scans `/gnw/`** and only lists games whose `.gnw` is present
  on the SD.
- **`case/*.png`** — case preview (PNG 256x192, decoded at runtime with
  stb_image) shown by the menu on the top screen for the selected game, loaded
  from `/gnw/case/`. If missing, the menu still works but that preview stays
  **black** (it does not crash).

They are generated with `shrinker/shrink_gnw.py` (`.gnw`) and
`shrinker/build_gnw_case.py` (`case/*.png`) and copied to `/gnw/` and `/gnw/case/`
on the SD, just like `build_ds.py` does with the melonDS virtual SD. It is the
same structure, so any DLDI flashcart runs the same `.nds`.

## Controls

### Main menu

| Action        | Key               |
| ------------- | ----------------- |
| Move cursor   | D-pad up/down     |
| Play          | A                 |

Inside any game, **R** returns to the main menu leaving **the last game you
were playing preselected** (the list scrolls to it).

### Per-game controls

| Game & Watch    | Nintendo DS                |
| --------------- | -------------------------- |
| LEFT            | D-pad left (or Y)          |
| RIGHT           | D-pad right (or A)         |
| UP              | D-pad up (or X)            |
| DOWN            | D-pad down (or B)          |
| GAME A          | START                      |
| GAME B          | SELECT                     |
| TIME            | L                          |
| ALARM           | L + R                      |

The **D-pad** is the main control. The face buttons `Y`/`A` (and `X`/`B` on the
games with UP/DOWN) are **shortcuts** for the same direction, meant for games
where pressing a button is more comfortable than the D-pad.

**R** returns to the main menu and leaves **the last game you were playing
preselected**. To avoid exiting accidentally, the **ALARM** fires with **L+R**:
if you keep `L` held and release `R`, you do not return to the menu.

**GAME B** (SELECT) does not exist on the single GAME button games (e.g.
Balloon Fight, Climber or Super Mario Bros.): there SELECT does nothing.

The most common control schemes:

- **D-pad + A = JUMP** (and X/B for UP/DOWN): Donkey Kong (II), Zelda,
  Balloon Fight, Crab Grab, Bomb Sweeper, Squish, ...
- **LEFT/RIGHT**: Fire, Lifeboat, Turtle Bridge, Tropical Fish, ...
- **4 corner buttons -> D-pad diagonals**: on these games (Ball, Chef, Judge,
  Lion, Mickey Mouse, Fire Attack, Flagman, Black Jack, Manhole, Mario Bros.)
  the G&W has 4 corner buttons. They map to the D-pad: ↑/↓ fire the left
  corners and X/B the right ones, according to the MAME `INPUT_PORTS`.
- **Lifeboat**: only LEFT/RIGHT (A or D-pad-right → RIGHT, Y or D-pad-left → LEFT).

## Editor: clangd (VS Code)

The project uses [clangd](https://marketplace.visualstudio.com/items?itemName=llvm-vs-code-extensions.vscode-clangd)
(configuration in `.clangd` and `.vscode/settings.json`). Compile at least once
with `make COMPDB=1` so that `compile_commands.json` exists.

## Regenerating the per-game data

Everything is generated with a single script from the `shrinker/input/artwork/` and `shrinker/input/roms/`
ZIPs (no intermediate versioned assets):

> **Note:** the ROMs used for the builds are the **MAME 0.289** ones in
> **NONMERGED** state, and the artworks are those of
> [DarthMarino](https://drive.google.com/drive/folders/1vl9O-0jIGCHHY_lrWpOwBtqTXEKsVGOY?usp=drive_link).

```bash
python shrinker/shrink_gnw.py               # -> shrinker/output/gnw/gnw_<game>.gnw for all 56 games
python shrinker/shrink_gnw.py cgrab ssparky # or just a subset (accepts games as arguments)
python shrinker/shrink_gnw.py --force mario # --force ignores the segment cache
```

`shrink_gnw.py` renders the LCD segments with Inkscape (SVGs from the `shrinker/input/roms/`
ZIP), composes the `topNS`/`bottomNS` backdrops with Pillow from the PNGs of
the `shrinker/input/artwork/` ZIP, and packs everything into the `.gnw` (program + geometry +
keyboard + the two backdrops in `background_pixel`; the SM511/512 include their
melody). The geometry uses `contain`: each screen (single or each half of a
dual) keeps the real artwork aspect ratio and is centered on its physical
screen; on duals the two screens stay contiguous (game continuity). The segment
antialias is kept as 4-bit intensity (`G>>4`) and displayed with `rgb_multiply`,
same as in LCD-Game-Shrinker/Emulator. The rendered PNGs stay in
`shrinker/build/<game>/` as a cache (reused on later builds).

Additionally, the **case previews** (PNG) are generated with a separate script:

```bash
python shrinker/build_gnw_case.py                 # -> shrinker/output/gnw/case/gnw_<game>.png for all
python shrinker/build_gnw_case.py --only pchute   # or just one game
```

`build_gnw_case.py` composites the case artwork (PNG from the `shrinker/input/artwork/` ZIP)
with the LCD (backdrop + segments) pasted into its window/hole, and generates
the `gnw/case/gnw_<game>.png` image (256x192, white background), which the
menu decodes from `/gnw/case/` on the SD with stb_image. It is
**independent** of `shrink_gnw.py` (it reuses its configurations and render
functions via import), so it must be run separately.

## Acknowledgments

Thanks to **bzhxx** for his fantastic LCD emulator, to the whole **MAME** team
for such an incredible project, and to **DarthMarino** for his beautiful artwork.

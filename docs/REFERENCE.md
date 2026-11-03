# GameNWatchDS technical reference

Homebrew emulator for the Nintendo DS that brings together Game & Watch games
in a single ROM, selectable from a main menu:

| Game                               | Model     | CPU      | Screens | File                                    |
| ---------------------------------- | --------- | -------- | ------- | --------------------------------------- |
| Ball                               | AC-01     | SM5A     | 1       | Ball.gnw                                |
| Balloon Fight                      | BF-107    | SM511    | 1       | Balloon Fight.gnw                       |
| Balloon Fight (Crystal Screen)     | BF-803    | SM511    | 1       | Balloon Fight (Crystal).gnw             |
| Black Jack                         | BJ-60     | SM512    | 2       | Black Jack.gnw                          |
| Bomb Sweeper                       | BD-62     | SM512    | 2       | Bomb Sweeper.gnw                        |
| Boxing                             | BX-301    | SM511    | 1       | Boxing.gnw                              |
| Chef                               | FP-24     | SM5A     | 1       | Chef.gnw                                |
| Climber                            | DR-106    | SM511    | 1       | Climber.gnw                             |
| Climber (Crystal Screen)           | DR-802    | SM511    | 1       | Climber (Crystal).gnw                   |
| Crab Grab                          | UD-202    | SM510    | 1       | Crab Grab.gnw                           |
| Donkey Kong Hockey                 | HK-303    | SM511    | 1       | Donkey Kong Hockey.gnw                  |
| Donkey Kong Jr.                    | DJ-101    | SM510    | 1       | Donkey Kong Jr.gnw                      |
| Donkey Kong Jr. (Panorama)         | CJ-93     | SM511    | 1       | Donkey Kong Jr. (Panorama).gnw          |
| Donkey Kong                        | DK-52     | SM510    | 2       | Donkey Kong.gnw                         |
| Donkey Kong 3                      | AK-302    | SM511    | 1       | Donkey Kong 3.gnw                       |
| Donkey Kong Circus                 | MK-96     | SM511    | 1       | Donkey Kong Circus.gnw                  |
| Donkey Kong II                     | JR-55     | SM510    | 2       | Donkey Kong II.gnw                      |
| Egg                                | MC-25     | SM5A     | 1       | Egg.gnw                                 |
| Fire                               | FR-27     | SM5A     | 1       | Fire.gnw                                |
| Fire (Silver)                      | RC-04     | SM5A     | 1       | Fire (Silver).gnw                       |
| Fire Attack                        | ID-29     | SM510    | 1       | Fire Attack.gnw                         |
| Flagman                            | FL-02     | SM5A     | 1       | Flagman.gnw                             |
| Gold Cliff                         | MV-64     | SM512    | 2       | Gold Cliff.gnw                          |
| Green House                        | GH-54     | SM510    | 2       | Green House.gnw                         |
| Helmet                             | CN-07     | SM5A     | 1       | Helmet.gnw                              |
| Judge                              | IP-05     | SM5A     | 1       | Judge.gnw                               |
| Lifeboat                           | TC-58     | SM510    | 2       | Lifeboat.gnw                            |
| Lion                               | LN-08     | SM5A     | 1       | Lion.gnw                                |
| Manhole                            | NH-103    | SM510    | 1       | Manhole.gnw                             |
| Manhole (Gold)                     | MH-06     | SM5A     | 1       | Manhole (Gold).gnw                      |
| Mario Bros.                        | MW-56     | SM510    | 2       | Mario Bros.gnw                          |
| Mario Cement Factory               | ML-102    | SM510    | 1       | Mario Cement Factory.gnw                |
| Mario Cement Factory (Tabletop)    | CM-72     | SM511    | 1       | Mario Cement Factory (Tabletop).gnw     |
| Mario the Juggler                  | MB-108    | SM511    | 1       | Mario the Juggler.gnw                   |
| Mario's Bombs Away                 | TB-94     | SM511    | 1       | Mario's Bombs Away.gnw                  |
| Mickey & Donald                    | DM-53     | SM510    | 2       | Mickey & Donald.gnw                     |
| Mickey Mouse                       | MC-25     | SM5A     | 1       | Mickey Mouse.gnw                        |
| Mickey Mouse (Panorama)            | DC-95     | SM511    | 1       | Mickey Mouse (Panorama).gnw             |
| Octopus                            | OC-22     | SM5A     | 1       | Octopus.gnw                             |
| Oil Panic                          | OP-51     | SM510    | 2       | Oil Panic.gnw                           |
| Parachute                          | PR-21     | SM5A     | 1       | Parachute.gnw                           |
| Pinball                            | PB-59     | SM511    | 2       | Pinball.gnw                             |
| Popeye                             | PP-23     | SM5A     | 1       | Popeye.gnw                              |
| Popeye (Panorama)                  | PG-92     | SM511    | 1       | Popeye (Panorama).gnw                   |
| Rain Shower                        | LP-57     | SM510    | 2       | Rain Shower.gnw                         |
| Safe Buster                        | JB-63     | SM511    | 2       | Safe Buster.gnw                         |
| Snoopy (Panorama)                  | SM-91     | SM511    | 1       | Snoopy (Panorama).gnw                   |
| Snoopy Tennis                      | SP-30     | SM510    | 1       | Snoopy Tennis.gnw                       |
| Squish                             | MG-61     | SM510    | 2       | Squish.gnw                              |
| Super Mario Bros.                  | YM-105    | SM511    | 1       | Super Mario Bros.gnw                    |
| Super Mario Bros. (Crystal Screen) | YM-801    | SM511    | 1       | Super Mario Bros. (Crystal).gnw         |
| Super Sparky                       | BU-201    | SM510    | 1       | Super Sparky.gnw                        |
| Tropical Fish                      | TF-104    | SM510    | 1       | Tropical Fish.gnw                       |
| Turtle Bridge                      | TL-28     | SM510    | 1       | Turtle Bridge.gnw                       |
| Vermin                             | MT-03     | SM5A     | 1       | Vermin.gnw                              |
| Zelda                              | ZL-65     | SM512    | 2       | Zelda.gnw                               |

Based on the handheld G&W emulators by [bzhxx](https://github.com/bzhxx).
Supports games with SM500, SM5A, SM510, SM511 and SM512 CPUs (the SM511/512
include their melody).

**Nothing is embedded in the `.nds`**: each game is a self-contained `.gnw`
file (SM5xx program + LCD geometry + keyboard table + the TWO RGB565 backdrops)
read from the SD card in the `/gnw/` folder. The `.nds` weighs about 160 KiB.
With TWiLight Menu++ the `.gnw` files can also be opened directly from its file
browser: see [Playing `.gnw` from TWiLight Menu++](#playing-gnw-from-twilight-menu).

## Project structure

```
GameNWatchDS/
├── Makefile / Makefile.arm9 / Makefile.arm7   # Build with BlocksDS
├── GNWBuilder.exe                             # Official Windows .gnw generator
├── gnw/                                      # Generated .gnw packages (NOT versioned)
├── arm7/source/main.c                         # ARM7 core (standard services)
├── arm9/source/
│   ├── main.c                                 # Menu, or direct launch from a loader
│   ├── launcher.c/h                           # Argument given by the loader (TWiLight Menu++)
│   ├── menu.c/h                               # Game selection (auto-scan of /gnw/)
│   ├── emulator.c/h                           # Unified common core
│   ├── games.h / games.c                      # Game catalog
│   ├── games/game_*.c                         # Per-game config (keys, tate...)
│   ├── gw_sys/                                # Game&Watch layer (shared)
│   └── cpus/                                  # SM5xx cores (shared)
├── artwork/                              # Original artwork ZIPs (NOT versioned)
├── roms/                                 # MAME NONMERGED ZIPs, one per machine (NOT versioned)
├── GNWBuilder/                           # Generator sources, build script, dependencies and tests
└── twilight/_nds/                        # Files to copy to the SD for TWiLight Menu++
```

`artwork/` and `roms/` hold the original ZIPs (`gnw_<game>.zip`) and are **not
versioned** (they are the local source used to regenerate the `.gnw`). `roms/`
must be the MAME 0.289 **NONMERGED** set (one self-contained ZIP per machine);
`GNWBuilder` validates every selected ZIP before generating anything. The whole
emulator and its data are generated from them with `GNWBuilder.exe`.

### On the SD card (Nintendo DSi / flashcart)

```
/gnw/
├── Ball.gnw       (Ball)
├── Donkey Kong.gnw      (Donkey Kong)
├── Fire.gnw       (Fire)
├── Super Mario Bros.gnw       (Super Mario Bros.)
└── ... (one .gnw per game, using its menu entry as the filename)
```

If a menu title ends in a period, that period also serves as the separator
before the `.gnw` extension (for example, `Mario Bros.gnw`).

Each `.gnw` is self-contained. The `background_pixel` header field stores the
two RGB565 backdrops concatenated (`topNS` + `bottomNS`, 98304 B each).
`gw_romloader_load_file()` reads the file, `gw_romloader_load()` validates it
and `gw_rom_backdrop(i)` exposes the backdrops to the renderer. Validation
includes exact core/geometry sizes, non-overlapping blocks, all 256 segment
rectangles and their packed-pixel ranges. Historical nine-row keyboard tables
are accepted and safely zero-extended internally to ten rows.

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
MSYS2) and **Inkscape** (to render the segment SVGs). `GNWBuilder.exe` already
contains Python, Pillow and NumPy.

Install the Python dependencies only when rebuilding GNWBuilder or running the
development tests:

```powershell
py -3 -m pip install -r requirements-dev.txt
```

```powershell
# 1) Generate the self-contained .gnw files from the input ZIPs
.\GNWBuilder.exe                 # graphical interface (Explorer or terminal)
.\GNWBuilder.exe --only fire     # a single game from a terminal
.\GNWBuilder.exe --force         # all games, re-rendering segments without cache

# 2) Compile the .nds (~160 KiB, no embedded ROMs)
make           # incremental build
make rebuild   # clean build
make compdb    # clean build plus compile_commands.json
make clean     # remove build artifacts
```

### GNWBuilder for Windows

`GNWBuilder.exe` is the official `.gnw` generator. It embeds Python, Pillow and
NumPy, while using the Inkscape installation already present on Windows.
It is a native graphical application and does not open a command-prompt window.
Double-click it to choose independent
ROM ZIP, artwork ZIP and `.gnw` output folders, select games, force a rebuild,
follow progress, cancel safely, or open the output folder. Folder selections
are deliberately not saved between runs. Every game row reports whether its
ROM ZIP is a complete MAME NONMERGED set; incomplete or merged ZIPs keep the
game disabled with the reason shown. If the windowed build hits an unexpected
error, the traceback is written to `%TEMP%\GNWBuilder-error.log`.

Its default folders are:

```text
roms
artwork
gnw
```

Inkscape 1.4.4 is the validated version. The builder searches `INKSCAPE`,
`PATH`, the Windows application registry and the standard `Program Files`
locations. Run `.\GNWBuilder\build_gnw_builder.ps1` to rebuild the versioned EXE
at the project root in an isolated environment. Its Python sources and tests
live in `GNWBuilder/`; the build also uses the shared `icon.gif` and
`arm9/source/games/` descriptors from the project root.

The Makefiles are the only build interface. They prefer the current BlocksDS
installation bundled under Wonderful and fall back to the historical
`C:/msys64/opt/blocksds` tree. Explicit `BLOCKSDS`, `BLOCKSDSEXT` and
`WONDERFUL_TOOLCHAIN` environment values always win. On Linux they use the
standard `/opt/wonderful` and `/opt/blocksds` locations.

GNWBuilder finds Inkscape on `PATH`, in the Windows application registry and in
the standard Windows installation locations. Set `INKSCAPE` to an executable
name or full path to override discovery (do not include command-line arguments):

```powershell
$env:INKSCAPE = 'C:\custom tools\inkscape.com'
.\GNWBuilder.exe --only fire
```

A failed Inkscape query or missing segment coordinates stops generation rather
than producing an incomplete LCD.

Run the generator regressions without commercial ROMs or artwork:

```bash
python -m unittest discover -s GNWBuilder/tests -v
```

The synthetic tests cover fresh caches, executable discovery, failed queries
and segment cropping, plus cache invalidation and command-line errors. Real SVG
export tests also run when `inkscape` is on `PATH` or configured through
`INKSCAPE`.

To audit the source keyboard tables against a local MAME checkout:

```bash
python tests/check_mame_inputs.py --engine --mame-source /path/to/mame/src/mame/handheld/hh_sm510.cpp
```

Without `--engine` it reads the generated `.gnw` files in `gnw/`, resolving each
package through the game catalog (menu title, not a `gnw_*` filename).

The `.gnw` files are generated in `gnw/`. Segment caches and previews are kept
under `build/gnw-builder/`; that folder is not versioned. The menu auto-scans
`/gnw/` and only lists games whose `.gnw` is
present on the SD card, so a missing `.gnw` simply means the game does not appear
in the list.

> **melonDS** (PC testing only): enable the SD card in its settings
> (Config → Firmware Settings → SD card) pointing to `C:\melonDS\SD`.
> Copy the regenerated `.gnw` files to its `/gnw/` directory so that
> `fopen("/gnw/...")` finds them.

## Usage on a flashcart (real Nintendo DS)

The emulator is a standard libnds homebrew and runs on any flashcart that
executes `.nds` (R4, Acekard 2/i, DSTT, GoldR, M3, ...) with the SD in
**FAT16/32** and its **DLDI** driver. Nothing special is required.

On the root of the SD card:

```
GameNWatchDS.nds   # launched from the flashcart menu
gnw/
├── Ball.gnw       # .gnw = gameplay (if missing, the game does not appear in the menu)
├── Chef.gnw
└── ...
```

- **`.gnw`** — game data (SM5xx program + geometry + keyboard + backdrops).
  The menu **auto-scans `/gnw/`** and only lists games whose `.gnw` is present
  on the SD.

They are generated with `GNWBuilder.exe` and copied to `/gnw/` on the
SD. It is the same structure, so any DLDI flashcart runs the same `.nds`.

## Playing `.gnw` from TWiLight Menu++

Pressing **A** on a `.gnw` in TWiLight Menu++ starts the game **directly**, with
no menu: the file browser launches `GameNWatchDS.nds` giving it the ROM as its
argument (`argv[1] = "sd:/roms/gnw/Donkey Kong.gnw"`), the same protocol
PicoDriveTWL uses for `.md`/`.gen` ROMs. Inside a game, **R** returns to
TWiLight Menu++.

Files to copy to the root of the SD card:

```
_nds/TWiLightMenu/emulators/GameNWatchDS.nds   # the emulator (make)
_nds/TWiLightMenu/extras/config.gnw.ini        # opens .gnw with it (twilight/_nds/)
roms/gnw/Donkey Kong.gnw                         # the games, in any folder
roms/gnw/Fire.gnw
```

`config.gnw.ini` is in this repository, at
`twilight/_nds/TWiLightMenu/extras/config.gnw.ini`; it uses the
**custom launchers** of TWiLight Menu++ (`config.<ext>.ini` files in
`/_nds/TWiLightMenu/extras/`), introduced in
[TWiLight Menu++ v27.25.0](https://github.com/DS-Homebrew/TWiLightMenu/releases/tag/v27.25.0).
Direct `.gnw` launch requires v27.25.0 or newer. TWiLight Menu++ only lists an extension whose config names a launcher that exists on the
card, so the `.nds` must be in `/_nds/TWiLightMenu/emulators/`.

The `.gnw` folder is free (`/gnw/`, `/roms/gnw/`, ...): the CPU and the ROM
signature in the header identify the game for both direct launch and the
internal menu. Renaming a package to another game's usual filename does not
change its controls or screen layout. Only our own
`.gnw` (the ones generated by `GNWBuilder.exe`) can be opened that way;
any other file gets a notice on screen and the emulator returns to the launcher.

On TWiLight Menu++ versions without custom launchers a single game can still be
opened with an `.argv` text file (`<rom>.gnw.argv`) whose first line is the
emulator and whose second line is the ROM:

```
/_nds/TWiLightMenu/emulators/GameNWatchDS.nds
/roms/gnw/Donkey Kong.gnw
```

Without a file argument (launched from a flashcard menu or from TWiLight Menu++
Homebrew Launcher) the emulator behaves exactly as before: the internal menu of
`/gnw/` is shown and **R** returns to it.

Before a release, perform the hardware-only acceptance pass that automated PC
tests cannot replace:

- DS/DS Lite with a DLDI flashcart: catalog boot, one game, audio and return.
- DSi in DS mode: the same catalog flow from `fat:`.
- DSi in DSi mode: boot from `sd:` and confirm the configured CPU boost.
- TWiLight Menu++: launch a normal and a renamed `.gnw` directly, then return
  with **R**.

> On a DSi the emulator runs in DSi mode and the SD card is `sd:`; on a DS
> flashcard it is `fat:`. The argument is resolved against both, so both cases
> work. If the `.nds` does not start or does not find the `.gnw`, the values to
> touch in `config.gnw.ini` are `DS_MODE`, `BOOST_CPU` and `RESOLVE`.

## Controls

### Main menu

The menu is a **plain text console** on the bottom screen (libnds
`consoleDemoInit`, the same approach RetroFabDS uses): the top screen stays
black, and the list shows 19 games at a time, left aligned and scrolling with
the selection, which is highlighted in another color.

| Action        | Key               |
| ------------- | ----------------- |
| Move cursor   | D-pad up/down     |
| Play          | A                 |

Inside any game, **R** returns to the main menu leaving **the last game you
were playing preselected** (the list scrolls to it).

### Per-game controls

| Game & Watch | Nintendo DS        |
| ------------ | ------------------ |
| LEFT         | D-pad left (or Y)  |
| RIGHT        | D-pad right (or A) |
| UP           | D-pad up (or X)    |
| DOWN         | D-pad down (or B)  |
| GAME A       | START             |
| GAME B       | SELECT            |
| TIME         | L                 |
| ALARM        | L + R             |

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

## MAME ROM inputs (NONMERGED)

The builds use the **MAME 0.289 NONMERGED** ROM set. In that distribution every
machine has its own self-contained ZIP, so `roms/` must contain exactly one
`gnw_<machine>.zip` per supported game:

```text
roms/
├── gnw_dkong.zip        # dk-52 + gnw_dkong_top.svg + gnw_dkong_bottom.svg
├── gnw_zelda.zip        # zl-65.program + zl-65.melody + the two SVGs
├── gnw_bfightn.zip      # the clone has its own ZIP (bf-107.program + bf-107.melody)
└── ...                  # 56 machines, one ZIP each
```

Each ZIP must contain the program ROM, the melody ROM for SM511/SM512 (256
bytes) and the SVG artwork of every screen. `GNWBuilder` validates this before
generating anything and stops with an actionable message when:

- a ZIP is missing, corrupt or incomplete (for example, a clone taken from a
  split/merged container without its melody or SVG);
- the ZIP still holds several program/melody dumps (a merged container);
- the program is larger than 4096 bytes or the melody is not 256 bytes;
- the SVG artwork referenced by the game configuration is absent.

Do not point `roms/` at a merged MAME set: merged ZIPs do not exist for clone
machines and the builder reads one ZIP per machine. The alternate dumps present
in the 0.289 set (`gnw_helmeto`, `gnw_judgeo`, `gnw_mariocmta`) are not used by
this project. After replacing the ROM ZIPs, regenerate all `.gnw` files.

## Regenerating the per-game data

Everything is generated with `GNWBuilder.exe` from the root-level `artwork/`
and `roms/` ZIPs (no intermediate
versioned assets):

> **Note:** the ROMs used for the builds are the **MAME 0.289** ones in
> **NONMERGED** state (see [MAME ROM inputs](#mame-rom-inputs-nonmerged)), and
> the artworks are those of
> [DarthMarino](https://drive.google.com/drive/folders/1vl9O-0jIGCHHY_lrWpOwBtqTXEKsVGOY?usp=drive_link).

```powershell
.\GNWBuilder.exe                         # graphical interface
.\GNWBuilder.exe cgrab ssparky          # generate a subset from a terminal
.\GNWBuilder.exe --force mario          # ignore the segment cache
```

`GNWBuilder.exe` renders the LCD segments with Inkscape (SVGs from the `roms/`
ZIP), composes the `topNS`/`bottomNS` backdrops with
Pillow from the PNGs of
the `artwork/` ZIP, and packs everything into the `.gnw` (program + geometry +
keyboard + the two backdrops in `background_pixel`; the SM511/512 include their
melody). The geometry uses `contain`: each screen (single or each half of a
dual) keeps the real artwork aspect ratio and is centered on its physical
screen; on duals the two screens stay contiguous (game continuity). The segment
reflector of every horizontal or vertical dual uses the lighter metal-plate
color detected between its two backdrops on both screens, avoiding a visible
tone change at the hinge while preserving each screen's artwork. The segment
antialias is kept as 4-bit intensity (`G>>4`) and displayed with `rgb_multiply`,
same as in LCD-Game-Shrinker/Emulator. Segment PNGs are exported in batches
through Inkscape's interactive `--shell` mode (one process per 32 segments,
with automatic per-segment fallback), so a cold build does not pay Inkscape's
startup cost once per LCD segment. The rendered PNGs stay in
`build/gnw-builder/cache/gnw_<game>/` as a cache (reused on later builds), and
the previews are written to `build/gnw-builder/preview/`.

Cache stamps include the LCD export mode; changing that mode or losing a stamp
regenerates the affected images automatically. The first build after this cache
format update re-exports segment PNGs. Invalid game names, incomplete options
and missing or non-NONMERGED input ZIPs stop generation before any selected
game is built.

## Acknowledgments

Thanks to **bzhxx** for his fantastic LCD emulator, to the whole **MAME** team
for such an incredible project, and to **DarthMarino** for his beautiful artwork.


### Menu discovery and load errors

The menu scans `.gnw` files in `/gnw/` and identifies each game by its CPU and
ROM signature, regardless of the filename. Renamed packages display the correct
game title and launch from their actual path. Multiple packages for the same
game appear once; the lexicographically first path is tried first. If loading
fails, the menu tries the remaining copies of that game in filename order.
Only after all alternatives fail is one notice shown. Files with unreadable,
truncated or unrecognized identity headers are omitted from the menu.

Load notices distinguish files that cannot be opened, SD read errors, invalid
packages and unknown games. A recognized header alone does not guarantee a valid
package: full validation runs when the game is launched.

SM511/SM512 packages must contain 256 bytes of valid melody commands. Failed
file or memory loads clear the active package, its pointers and backdrops;
an invalid melody is reported as an invalid package before emulation starts.

## Repository conventions

See the [documentation index](README.md), [folder and file conventions](PROJECT_LAYOUT.md),
[test index](../tests/README.md) and [development tools](../tools/README.md).

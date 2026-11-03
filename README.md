# GameNWatchDS

Play 56 Game & Watch games on Nintendo DS, DS Lite and DSi.
Choose a game from the menu, or open a `.gnw` file directly with a compatible
version of TWiLight Menu++.

## 1. Download

**[Download the latest release](https://github.com/dsaltiveri/GameNWatchDS/releases/latest)**
and extract `GameNWatchDS-v1.0.0.zip` on your PC.

The ZIP includes:

| File | What it does |
| --- | --- |
| `GameNWatchDS.nds` | Emulator to copy to your SD card |
| `GNWBuilder.exe` | Windows app that converts your ROMs and artwork into `.gnw` games |
| `twilight/` | Configuration for opening games directly in TWiLight Menu++ |

You do not need to compile anything or install Python. To convert games, install
[Inkscape](https://inkscape.org/release/) on Windows (validated with version 1.4.4).
ROMs, artwork and converted games are not included.

## 2. Convert your games

You need **MAME 0.289 NONMERGED** ROM ZIPs and the matching Game & Watch artwork
ZIPs by [DarthMarino](https://drive.google.com/drive/folders/1vl9O-0jIGCHHY_lrWpOwBtqTXEKsVGOY?usp=drive_link).
Keep the ZIPs compressed. Each game needs its own complete ROM ZIP, including
its melody where applicable; merged and split ROM sets are not supported.

1. Put your ROM ZIPs in one folder and your artwork ZIPs in another.
   Both use names such as `gnw_dkong.zip` and `gnw_fire.zip`.
2. Open `GNWBuilder.exe`.
3. Choose the **ROM**, **artwork** and **output** folders.
4. Select the games you want and start generation. If a ROM is incomplete,
   the app explains why that game cannot be selected.
5. Wait for generation to finish. The output folder will contain files such
   as `Donkey Kong.gnw` and `Fire.gnw`.

Folder selections are not saved between runs. Each `.gnw` contains everything
needed to play that game; copy these files to the console, keeping the original
ROM and artwork ZIPs on your PC.

### Supported games

ROM ZIPs must be from the **MAME 0.289 NONMERGED** set. ROM and artwork ZIPs
share the filename shown below, but are different files: select them from
separate folders in GNWBuilder. The File column shows the generated `.gnw`
package to copy to your SD card.

| Game                               | Model  | CPU   | Screens | File                                | ROM / Artwork ZIP |
| ---------------------------------- | ------ | ----- | ------- | ----------------------------------- | ----------------- |
| Ball                               | AC-01  | SM5A  | 1       | Ball.gnw                            | gnw_ball.zip      |
| Balloon Fight                      | BF-107 | SM511 | 1       | Balloon Fight.gnw                   | gnw_bfightn.zip   |
| Balloon Fight (Crystal Screen)     | BF-803 | SM511 | 1       | Balloon Fight (Crystal).gnw         | gnw_bfight.zip    |
| Black Jack                         | BJ-60  | SM512 | 2       | Black Jack.gnw                      | gnw_bjack.zip     |
| Bomb Sweeper                       | BD-62  | SM512 | 2       | Bomb Sweeper.gnw                    | gnw_bsweep.zip    |
| Boxing                             | BX-301 | SM511 | 1       | Boxing.gnw                          | gnw_boxing.zip    |
| Chef                               | FP-24  | SM5A  | 1       | Chef.gnw                            | gnw_chef.zip      |
| Climber                            | DR-106 | SM511 | 1       | Climber.gnw                         | gnw_climbern.zip  |
| Climber (Crystal Screen)           | DR-802 | SM511 | 1       | Climber (Crystal).gnw               | gnw_climber.zip   |
| Crab Grab                          | UD-202 | SM510 | 1       | Crab Grab.gnw                       | gnw_cgrab.zip     |
| Donkey Kong Hockey                 | HK-303 | SM511 | 1       | Donkey Kong Hockey.gnw              | gnw_dkhockey.zip  |
| Donkey Kong Jr.                    | DJ-101 | SM510 | 1       | Donkey Kong Jr.gnw                  | gnw_dkjr.zip      |
| Donkey Kong Jr. (Panorama)         | CJ-93  | SM511 | 1       | Donkey Kong Jr. (Panorama).gnw      | gnw_dkjrp.zip     |
| Donkey Kong                        | DK-52  | SM510 | 2       | Donkey Kong.gnw                     | gnw_dkong.zip     |
| Donkey Kong 3                      | AK-302 | SM511 | 1       | Donkey Kong 3.gnw                   | gnw_dkong3.zip    |
| Donkey Kong Circus                 | MK-96  | SM511 | 1       | Donkey Kong Circus.gnw              | gnw_dkcirc.zip    |
| Donkey Kong II                     | JR-55  | SM510 | 2       | Donkey Kong II.gnw                  | gnw_dkong2.zip    |
| Egg                                | MC-25  | SM5A  | 1       | Egg.gnw                             | gnw_egg.zip       |
| Fire                               | FR-27  | SM5A  | 1       | Fire.gnw                            | gnw_fire.zip      |
| Fire (Silver)                      | RC-04  | SM5A  | 1       | Fire (Silver).gnw                   | gnw_fires.zip     |
| Fire Attack                        | ID-29  | SM510 | 1       | Fire Attack.gnw                     | gnw_fireatk.zip   |
| Flagman                            | FL-02  | SM5A  | 1       | Flagman.gnw                         | gnw_flagman.zip   |
| Gold Cliff                         | MV-64  | SM512 | 2       | Gold Cliff.gnw                      | gnw_gcliff.zip    |
| Green House                        | GH-54  | SM510 | 2       | Green House.gnw                     | gnw_ghouse.zip    |
| Helmet                             | CN-07  | SM5A  | 1       | Helmet.gnw                          | gnw_helmet.zip    |
| Judge                              | IP-05  | SM5A  | 1       | Judge.gnw                           | gnw_judge.zip     |
| Lifeboat                           | TC-58  | SM510 | 2       | Lifeboat.gnw                        | gnw_lboat.zip     |
| Lion                               | LN-08  | SM5A  | 1       | Lion.gnw                            | gnw_lion.zip      |
| Manhole                            | NH-103 | SM510 | 1       | Manhole.gnw                         | gnw_manhole.zip   |
| Manhole (Gold)                     | MH-06  | SM5A  | 1       | Manhole (Gold).gnw                  | gnw_manholeg.zip  |
| Mario Bros.                        | MW-56  | SM510 | 2       | Mario Bros.gnw                      | gnw_mario.zip     |
| Mario Cement Factory               | ML-102 | SM510 | 1       | Mario Cement Factory.gnw            | gnw_mariocm.zip   |
| Mario Cement Factory (Tabletop)    | CM-72  | SM511 | 1       | Mario Cement Factory (Tabletop).gnw | gnw_mariocmt.zip  |
| Mario the Juggler                  | MB-108 | SM511 | 1       | Mario the Juggler.gnw               | gnw_mariotj.zip   |
| Mario's Bombs Away                 | TB-94  | SM511 | 1       | Mario's Bombs Away.gnw              | gnw_mbaway.zip    |
| Mickey & Donald                    | DM-53  | SM510 | 2       | Mickey & Donald.gnw                 | gnw_mickdon.zip   |
| Mickey Mouse                       | MC-25  | SM5A  | 1       | Mickey Mouse.gnw                    | gnw_mmouse.zip    |
| Mickey Mouse (Panorama)            | DC-95  | SM511 | 1       | Mickey Mouse (Panorama).gnw         | gnw_mmousep.zip   |
| Octopus                            | OC-22  | SM5A  | 1       | Octopus.gnw                         | gnw_octopus.zip   |
| Oil Panic                          | OP-51  | SM510 | 2       | Oil Panic.gnw                       | gnw_opanic.zip    |
| Parachute                          | PR-21  | SM5A  | 1       | Parachute.gnw                       | gnw_pchute.zip    |
| Pinball                            | PB-59  | SM511 | 2       | Pinball.gnw                         | gnw_pinball.zip   |
| Popeye                             | PP-23  | SM5A  | 1       | Popeye.gnw                          | gnw_popeye.zip    |
| Popeye (Panorama)                  | PG-92  | SM511 | 1       | Popeye (Panorama).gnw               | gnw_popeyep.zip   |
| Rain Shower                        | LP-57  | SM510 | 2       | Rain Shower.gnw                     | gnw_rshower.zip   |
| Safe Buster                        | JB-63  | SM511 | 2       | Safe Buster.gnw                     | gnw_sbuster.zip   |
| Snoopy (Panorama)                  | SM-91  | SM511 | 1       | Snoopy (Panorama).gnw               | gnw_snoopyp.zip   |
| Snoopy Tennis                      | SP-30  | SM510 | 1       | Snoopy Tennis.gnw                   | gnw_stennis.zip   |
| Squish                             | MG-61  | SM510 | 2       | Squish.gnw                          | gnw_squish.zip    |
| Super Mario Bros.                  | YM-105 | SM511 | 1       | Super Mario Bros.gnw                | gnw_smbn.zip      |
| Super Mario Bros. (Crystal Screen) | YM-801 | SM511 | 1       | Super Mario Bros. (Crystal).gnw     | gnw_smb.zip       |
| Super Sparky                       | BU-201 | SM510 | 1       | Super Sparky.gnw                    | gnw_ssparky.zip   |
| Tropical Fish                      | TF-104 | SM510 | 1       | Tropical Fish.gnw                   | gnw_tfish.zip     |
| Turtle Bridge                      | TL-28  | SM510 | 1       | Turtle Bridge.gnw                   | gnw_tbridge.zip   |
| Vermin                             | MT-03  | SM5A  | 1       | Vermin.gnw                          | gnw_vermin.zip    |
| Zelda                              | ZL-65  | SM512 | 2       | Zelda.gnw                           | gnw_zelda.zip     |

## 3. Copy to the SD card and play

### Flashcard or DSi SD card

Use a FAT16/FAT32 card with the appropriate launcher already installed:

| Where you play | Card to use | How to launch |
| --- | --- | --- |
| Flashcard (R4, Acekard, DSTT, etc.) | The microSD inside the flashcard | Open `GameNWatchDS.nds` from the flashcard's menu; DLDI support is required |
| DSi without a flashcard | The SD card inserted into the DSi's SD slot | Open `GameNWatchDS.nds` from TWiLight Menu++ |

1. Turn off the console, remove the appropriate card and connect it to your PC.
2. Copy `GameNWatchDS.nds` from the release ZIP to the card root.
3. Create a `gnw` folder at the card root and copy the `.gnw` files generated
   by GNWBuilder into it.

```text
SD / microSD card/
├── GameNWatchDS.nds
└── gnw/
    ├── Donkey Kong.gnw
    ├── Fire.gnw
    └── ...
```

4. Safely eject the card, put it back into the flashcard or DSi SD slot and
   turn on the console.
5. Launch `GameNWatchDS.nds` using the menu shown in the table above.
6. Select a game with **D-pad up/down**, then press **A** to play.

Press **R** during play to return to the emulator's menu, with your last game
still selected. Only games present in `/gnw/` appear. TWiLight Menu++ is optional
when using a flashcard's own menu.

To open individual `.gnw` files directly from TWiLight Menu++, follow the
alternative setup below.

### Playing `.gnw` from TWiLight Menu++

Opening `.gnw` files directly requires **TWiLight Menu++ v27.25.0 or newer**.
This version introduced the custom launchers used by `config.gnw.ini`.
Use the DSi SD card, or the flashcard's microSD if TWiLight Menu++ runs there.
Copy the emulator and the supplied configuration to these exact paths:

```text
SD card/
├── _nds/TWiLightMenu/
│   ├── emulators/GameNWatchDS.nds
│   └── extras/config.gnw.ini
└── roms/gnw/
    ├── Donkey Kong.gnw
    └── Fire.gnw
```

The configuration is included under `twilight/_nds/TWiLightMenu/extras/` in the
release. Browse to a `.gnw` in TWiLight Menu++ and press **A** to play. **R**
returns to TWiLight Menu++. Games can be stored in any folder for direct launch.

With TWiLight Menu++ older than v27.25.0, use the
emulator's own menu and keep games in `/gnw/` as shown above.

## Controls

| Game & Watch | Nintendo DS |
| --- | --- |
| LEFT | D-pad left (or Y) |
| RIGHT | D-pad right (or A) |
| UP | D-pad up (or X) |
| DOWN | D-pad down (or B) |
| JUMP / action | A, on games that use it |
| GAME A / GAME | START |
| GAME B | SELECT |
| TIME | L |
| ALARM | L + R |
| Return to menu / launcher | R |

Controls depend on the original game. Games with one GAME button do not use
SELECT. For games with four corner buttons, up/down control the left corners
and X/B the right corners.
To use ALARM without leaving the game, hold L while pressing and releasing R.

## Having trouble?

- **A game is missing from the menu:** check that its `.gnw` is in `/gnw/` at
  the SD card root and that conversion completed successfully.
- **GNWBuilder rejects a ROM:** use the complete MAME 0.289 NONMERGED ZIP for
  that machine, including the melody and SVG files required by the game.
- **Inkscape is not found:** install it in the standard Windows location and
  reopen GNWBuilder.
- **TWiLight Menu++ does not show `.gnw` files:** check its version and confirm
  both the emulator and `config.gnw.ini` are in the paths shown above.

## Development

See the [build instructions](docs/BUILDING.md) and [test guide](tests/README.md).

## Acknowledgments

Thanks to **[bzhxx](https://github.com/bzhxx)** for his fantastic LCD emulator, to the whole **[MAME](https://www.mamedev.org/)** team
for such an incredible project, and to **[DarthMarino](https://drive.google.com/drive/folders/1vl9O-0jIGCHHY_lrWpOwBtqTXEKsVGOY?usp=drive_link)** for his beautiful artwork.

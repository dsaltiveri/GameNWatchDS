/*
 * GameNWatchDS : Game & Watch emulator for the Nintendo DS.
 * Main menu with all the available games.
 * The .gnw ROMs are read from the SD card (/gnw/).
 *
 * When the loader passes a .gnw as argument (TWiLight Menu++ custom launchers,
 * .argv files...) the game boots directly, without this menu, and R gives the
 * control back to the loader.
 */
#include <nds.h>
#include <stdio.h>
#include <fat.h>

#include "menu.h"
#include "games.h"
#include "emulator.h"
#include "launcher.h"

/* Footer of the notices shown when the game cannot be opened. */
#define NOTICE_FOOTER "A: BACK TO THE LAUNCHER"

/* Distinguish SD/file errors from invalid packages and unknown games. */
static void show_load_error(const char *path, gw_load_error_t error,
                            const char *footer){
    const char *hint = error == GW_LOAD_OPEN_ERROR ? "THE FILE COULD NOT BE OPENED. CHECK THE SD CARD AND PATH" :
        error == GW_LOAD_READ_ERROR ? "COULD NOT READ THE FILE. CHECK THE SD CARD" :
        "THE .GNW FILE IS DAMAGED OR HAS AN INVALID FORMAT";
    menu_show_notice("COULD NOT LOAD", path, hint, footer);
}

/* Use the package identity for every entry point, including the SD menu. */
static const game_desc_t *game_from_header(const char *path){
    char cpu[9], sig[9];
    if (!launcher_read_rom_id(path, cpu, sig))
        return NULL;
    return games_find_by_rom(cpu, sig);
}

/* Boots the .gnw named in the command line. Returns 1 when there was an
   argument (the game has run or a notice is on screen) and 0 to show the menu. */
static int boot_from_loader(int argc, char **argv){
    const char *arg = launcher_arg_path(argc, argv);
    if (!arg)
        return 0;

    /* TWiLight Menu++ passes the file of the file browser as an absolute path
       ("sd:/roms/gnw/Donkey Kong.gnw", or "fat:/..." from a flashcard menu). */
    char resolved[LAUNCHER_PATH_MAX];
    const char *path = launcher_resolve(arg, resolved, sizeof(resolved));
    if (!path){
        show_load_error(arg, GW_LOAD_OPEN_ERROR, NOTICE_FOOTER);
        return 1;
    }

    /* The header determines controls and display layout even if this file
       has been renamed to another catalog game's usual filename. */
    const game_desc_t *g = game_from_header(path);
    if (!g){
        if (launcher_rom_error() != GW_LOAD_OK) {
            show_load_error(path, launcher_rom_error(), NOTICE_FOOTER);
            return 1;
        }
        menu_show_notice("UNKNOWN .GNW", path,
                         "THIS GAME IS NOT IN THE EMULATOR CATALOG", NOTICE_FOOTER);
        return 1;
    }

    if (!emulator_run_path(g, path))
        show_load_error(path, gw_romloader_error(), NOTICE_FOOTER);
    return 1;
}

int main(int argc, char **argv){
    if (isDSiMode())
        setCpuClock(true);

    /* Mounts the SD card (DLDI) so the .gnw files can be read. */
    menu_set_sd_ok(fatInitDefault());

    /* Opened from a file browser: play the game and return to it on exit. */
    if (boot_from_loader(argc, argv))
        return 0;

    /* Last played game, to preselect it in the menu when returning with R. */
    int last = -1;
    for(;;){
        int idx = menu_select(last);
        if(idx < 0 || idx >= game_count) break;
        /* Infinite game loop; returns 1 with R and 0 if the ROM could
           not be loaded (the .gnw is missing from the SD). */
        const char *path = menu_game_path(idx);
        if (!path) continue;
        for (;;){
            const game_desc_t *g = game_from_header(path);
            if(g && emulator_run_path(g, path)){
                last = idx;   /* actually played -> remember it */
                break;
            }
            /* Scanning alternatives reads more headers, so preserve the cause
               of this failure before the launcher's error state changes. */
            gw_load_error_t error = g ? gw_romloader_error() : launcher_rom_error();
            const char *next = menu_next_game_path(idx);
            if (next){
                path = next;
                continue;
            }
            if (!g && error == GW_LOAD_OK)
                menu_show_notice("UNKNOWN GAME", path,
                                 "THIS GAME IS NOT IN THE EMULATOR CATALOG",
                                 "A: BACK TO THE MENU");
            else
                show_load_error(path, error, "A: BACK TO THE MENU");
            break;
        }
    }
    return 0;
}


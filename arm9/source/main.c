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

/* Boots the .gnw named in the command line. Returns 1 when there was an
   argument (the game has run or a notice is on screen) and 0 to show the menu. */
static int boot_from_loader(int argc, char **argv){
    const char *arg = launcher_arg_path(argc, argv);
    if (!arg)
        return 0;

    /* TWiLight Menu++ passes the file of the file browser as an absolute path
       ("sd:/roms/gnw/gnw_dkong.gnw", or "fat:/..." from a flashcard menu). */
    char resolved[LAUNCHER_PATH_MAX];
    const char *path = launcher_resolve(arg, resolved, sizeof(resolved));
    if (!path){
        menu_show_notice("COULD NOT OPEN", arg, "THE FILE IS NOT ON THE SD CARD",
                         NOTICE_FOOTER);
        return 1;
    }

    /* The .gnw is identified by its file name; a renamed copy is recognised by
       the CPU and ROM signature of its own header. */
    const game_desc_t *g = games_find_by_file(path);
    if (!g){
        char cpu[9], sig[9];
        if (launcher_read_rom_id(path, cpu, sig))
            g = games_find_by_rom(cpu, sig);
    }
    if (!g){
        menu_show_notice("UNKNOWN .GNW", path,
                         "NOT A GAME & WATCH ROM FOR THIS EMULATOR", NOTICE_FOOTER);
        return 1;
    }

    if (!emulator_run_path(g, path))
        menu_show_notice("COULD NOT LOAD", path, "THE .GNW FILE IS DAMAGED",
                         NOTICE_FOOTER);
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
        if(emulator_run(games[idx]))
            last = idx;   /* actually played -> remember it */
        else
            menu_show_error(games[idx]->rom_path);
    }
    return 0;
}

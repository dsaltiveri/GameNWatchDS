/*
 * GameNWatchDS : Game & Watch emulator for the Nintendo DS.
 * Main menu with all the available games.
 * The .gnw ROMs are read from the SD card (/gnw/).
 */
#include <nds.h>
#include <stdio.h>
#include <fat.h>

#include "menu.h"
#include "games.h"
#include "emulator.h"

int main(void){
    /* Mounts the SD card (DLDI) so the .gnw files from /gnw/ can be read. */
    menu_set_sd_ok(fatInitDefault());

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

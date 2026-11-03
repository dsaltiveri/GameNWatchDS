/*
 * Lifeboat (TC-58, SM510, dual screen).
 * Keeps the key mapping from the gnw_lboat project.
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 lboat_update_buttons(void){
    u32 k=keysHeld(), b=0;
    /* Lifeboat only has LEFT/RIGHT: A or D-pad-right -> RIGHT,
       Y or D-pad-left -> LEFT */
    if((k&KEY_A) || (k&KEY_RIGHT)) b|=GW_BUTTON_RIGHT;
    if((k&KEY_Y) || (k&KEY_LEFT))  b|=GW_BUTTON_LEFT;
    /* GAME A -> START, GAME B -> SELECT, TIME -> L, ALARM -> R */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* GAME A */
    if(k&KEY_SELECT) b|=GW_BUTTON_B;      /* GAME B */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* TIME */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* ALARM */
    return b;
}

const game_desc_t game_lboat = {
    .name = "Lifeboat",
    .rom_path = "/gnw/Lifeboat.gnw",
    .cpu = ROM_CPU_SM510,
    .rom_sig = "w_lboat_",
    .dual_screen = 1,
    .main_uses_top = 1,
    .use_sm5a = 0,
    .init_screens = NULL,
    .update_buttons = lboat_update_buttons,
};

/*
 * Fire (FR-27, SM5A, single screen).
 * Keeps the key mapping and the SM5A render (per O/W outputs) from
 * the gnw_fire project. The LCD occupies only the top screen (MAIN); the
 * bottom screen stays black.
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 fire_update_buttons(void){
    u32 k=keysHeld(), b=0;
    /* Fire only has LEFT/RIGHT: A or D-pad-right -> RIGHT,
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

const game_desc_t game_fire = {
    .name = "Fire",
    .rom_path = "/gnw/Fire.gnw",
    .cpu = ROM_CPU_SM5A,
    .rom_sig = "w_fire__",
    .dual_screen = 0,          /* single LCD screen (MAIN) */
    .main_uses_top = 0,        /* MAIN shows bottomNS; SUB stays black */
    .use_sm5a = 1,
    .init_screens = NULL,
    .update_buttons = fire_update_buttons,
};

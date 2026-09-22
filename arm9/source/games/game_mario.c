/*
 * MARIO BROS (SM510, dual screen).
 * Key mapping per MAME hh_sm510.cpp.
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 mario_bros_update_buttons(void){
    u32 k=keysHeld(), b=0;
    /* 4 action buttons (colors) -> D-pad. */
    if(k&KEY_UP)     b|=GW_BUTTON_UP;
    if((k&KEY_X) || (k&KEY_RIGHT)) b|=GW_BUTTON_RIGHT; /* X = D-pad right */
    if(k&KEY_DOWN)   b|=GW_BUTTON_DOWN;
    if((k&KEY_B) || (k&KEY_LEFT))  b|=GW_BUTTON_LEFT;  /* B = D-pad left */
    /* GAME A -> START, GAME B -> SELECT, TIME -> L, ALARM -> R */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* GAME A */
    if(k&KEY_SELECT) b|=GW_BUTTON_B;      /* GAME B */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* TIME */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* ALARM */
    return b;
}

const game_desc_t game_mario = {
    .name = "Mario Bros.",
    .rom_path = "/gnw/gnw_mario.gnw",
    .cpu = ROM_CPU_SM510,
    .rom_sig = "w_mario_",
    .dual_screen = 1,
    .main_uses_top = 1,
    .use_sm5a = 0,
    .init_screens = NULL,
    .update_buttons = mario_bros_update_buttons,
};

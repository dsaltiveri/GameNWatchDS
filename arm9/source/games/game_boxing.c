/*
 * BOXING (SM511, single screen, SM511 melody).
 * Key mapping per MAME hh_sm510.cpp (2 punch buttons).
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 boxing_update_buttons(void){
    u32 k=keysHeld(), b=0;
    /* Joystick (arm up/down, left/right movement) + punch P1. */
    if(k&KEY_UP)     b|=GW_BUTTON_UP;
    if(k&KEY_DOWN)   b|=GW_BUTTON_DOWN;
    if(k&KEY_LEFT)   b|=GW_BUTTON_LEFT;
    if(k&KEY_RIGHT)  b|=GW_BUTTON_RIGHT;
    if(k&KEY_A)      b|=GW_BUTTON_A;   /* punch P1 */
    /* GAME A -> START, GAME B -> SELECT, TIME -> L, ALARM -> R */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* GAME A */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* TIME */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* ALARM */
    return b;
}

const game_desc_t game_boxing = {
    .name = "Boxing",
    .rom_path = "/gnw/gnw_boxing.gnw",
    .cpu = ROM_CPU_SM511,
    .rom_sig = "w_boxing",
    .dual_screen = 0,
    .main_uses_top = 0,
    .use_sm5a = 0,
    .init_screens = NULL,
    .update_buttons = boxing_update_buttons,
};

/*
 * PINBALL (SM511, dual screen, SM511 melody).
 * Key mapping per MAME hh_sm510.cpp.
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 pinball_update_buttons(void){
    u32 k=keysHeld(), b=0;
    /* LEFT/RIGHT (D-pad + Y/A), GAME A/B, TIME, ALARM. */
    if((k&KEY_A) || (k&KEY_RIGHT)) b|=GW_BUTTON_RIGHT;
    if((k&KEY_Y) || (k&KEY_LEFT))  b|=GW_BUTTON_LEFT;
    /* GAME A -> START, GAME B -> SELECT, TIME -> L, ALARM -> R */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* GAME A */
    if(k&KEY_SELECT) b|=GW_BUTTON_B;      /* GAME B */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* TIME */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* ALARM */
    return b;
}

const game_desc_t game_pinball = {
    .name = "Pinball",
    .rom_path = "/gnw/Pinball.gnw",
    .cpu = ROM_CPU_SM511,
    .rom_sig = "w_pinbal",
    .dual_screen = 1,
    .main_uses_top = 1,
    .use_sm5a = 0,
    .init_screens = NULL,
    .update_buttons = pinball_update_buttons,
};

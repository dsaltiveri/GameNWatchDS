/*
 * SNOOPY TENNIS (SM510, single screen).
 * Key mapping per MAME hh_sm510.cpp.
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 snoopy_tenni_update_buttons(void){
    u32 k=keysHeld(), b=0;
    /* UP/DOWN + A. */
    if((k&KEY_UP)   || (k&KEY_A)) b|=GW_BUTTON_UP;
    if((k&KEY_DOWN) || (k&KEY_Y)) b|=GW_BUTTON_DOWN;
    if(k&KEY_A)      b|=GW_BUTTON_A;
    /* GAME A -> START, GAME B -> SELECT, TIME -> L, ALARM -> R */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* GAME A */
    if(k&KEY_SELECT) b|=GW_BUTTON_B;      /* GAME B */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* TIME */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* ALARM */
    return b;
}

const game_desc_t game_stennis = {
    .name = "Snoopy Tennis",
    .rom_path = "/gnw/Snoopy Tennis.gnw",
    .cpu = ROM_CPU_SM510,
    .rom_sig = "w_snoopy",
    .dual_screen = 0,
    .main_uses_top = 0,
    .use_sm5a = 0,
    .init_screens = NULL,
    .update_buttons = snoopy_tenni_update_buttons,
};

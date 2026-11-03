/*
 * MICKEY MOUSE PANORAMA (SM511, single screen, inverted color LCD).
 * Key mapping per MAME hh_sm510.cpp.
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 mickey_panorama_update_buttons(void){
    u32 k=keysHeld(), b=0;
    /* LEFT/RIGHT (D-pad + Y/A). */
    if((k&KEY_A) || (k&KEY_RIGHT)) b|=GW_BUTTON_RIGHT;
    if((k&KEY_Y) || (k&KEY_LEFT))  b|=GW_BUTTON_LEFT;
    /* GAME A -> START, GAME B -> SELECT, TIME -> L, ALARM -> R */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* GAME A */
    if(k&KEY_SELECT) b|=GW_BUTTON_B;      /* GAME B */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* TIME */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* ALARM */
    return b;
}

const game_desc_t game_mmousep = {
    .name = "Mickey Mouse (Panorama)",
    .rom_path = "/gnw/Mickey Mouse (Panorama).gnw",
    .cpu = ROM_CPU_SM511,
    .rom_sig = "w_mmouse",
    .dual_screen = 0,
    .main_uses_top = 0,
    .use_sm5a = 0,
    .lcd_inverted = 1,
    .init_screens = NULL,
    .update_buttons = mickey_panorama_update_buttons,
};

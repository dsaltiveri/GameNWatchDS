/*
 * Mickey & Donald (DM-53, SM510, dual screen).
 * Keeps the key mapping from the gnw_mickdon project. The keyboard table
 * DM-53 already comes correct in the .gnw: S1 = d-pad, S2 = Time/GameB/GameA/Alarm
 * (no patch needed).
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 mickdon_update_buttons(void){
    u32 k=keysHeld(), b=0;
    if((k&KEY_A) || (k&KEY_RIGHT)) b|=GW_BUTTON_RIGHT;
    if((k&KEY_Y) || (k&KEY_LEFT))  b|=GW_BUTTON_LEFT;
    if((k&KEY_X) || (k&KEY_UP))    b|=GW_BUTTON_UP;
    if((k&KEY_B) || (k&KEY_DOWN))  b|=GW_BUTTON_DOWN;
    /* GAME A -> START, GAME B -> SELECT, TIME -> L, ALARM -> R */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* GAME A */
    if(k&KEY_SELECT) b|=GW_BUTTON_B;      /* GAME B */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* TIME */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* ALARM */
    return b;
}

const game_desc_t game_mickdon = {
    .name = "Mickey & Donald",
    .rom_path = "/gnw/gnw_mickdon.gnw",
    .cpu = ROM_CPU_SM510,
    .rom_sig = "w_mickdo",
    .dual_screen = 1,
    .main_uses_top = 1,
    .use_sm5a = 0,
    .init_screens = NULL,
    .update_buttons = mickdon_update_buttons,
};

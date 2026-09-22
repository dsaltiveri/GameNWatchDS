/*
 * Donkey Kong II (JR-55, SM510, dual screen).
 * Keeps the key mapping from the gnw_dkong2 project. The keyboard table
 * JR-55 already comes correct in the .gnw: S1 = JUMP (A), S2 = d-pad,
 * S3 = Time/GameB/GameA/Alarm (no patch needed, like mickdon/lboat).
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 dkong2_update_buttons(void){
    u32 k=keysHeld(), b=0;
    if(k&KEY_LEFT)   b|=GW_BUTTON_LEFT;
    if(k&KEY_UP)     b|=GW_BUTTON_UP;
    if(k&KEY_RIGHT)  b|=GW_BUTTON_RIGHT;
    if(k&KEY_DOWN)   b|=GW_BUTTON_DOWN;
    if(k&KEY_A)      b|=GW_BUTTON_A;       /* Jump */
    /* GAME A -> START, GAME B -> SELECT, TIME -> L, ALARM -> R */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* GAME A */
    if(k&KEY_SELECT) b|=GW_BUTTON_B;      /* GAME B */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* TIME */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* ALARM */
    return b;
}

const game_desc_t game_dkong2 = {
    .name = "Donkey Kong II",
    .rom_path = "/gnw/gnw_dkong2.gnw",
    .cpu = ROM_CPU_SM510,
    .rom_sig = "w_dkong2",
    .dual_screen = 1,
    .main_uses_top = 1,
    .use_sm5a = 0,
    .init_screens = NULL,
    .update_buttons = dkong2_update_buttons,
};

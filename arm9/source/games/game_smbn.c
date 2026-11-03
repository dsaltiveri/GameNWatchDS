/*
 * Super Mario Bros. (YM-105, SM511, single screen).
 * SM511 CPU (core already supported by gw_system). Keeps the key mapping
 * from MAME hh_sm510.cpp (INPUT_PORTS_START(gnw_smb)):
 *   S1 = Time/GAME/Alarm, S2 = d-pad, S3 = Jump.
 * The YM-105 only has ONE GAME button (no Game B): SELECT does nothing.
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 smbn_update_buttons(void){
    u32 k=keysHeld(), b=0;
    if(k&KEY_LEFT)   b|=GW_BUTTON_LEFT;
    if(k&KEY_UP)     b|=GW_BUTTON_UP;
    if(k&KEY_RIGHT)  b|=GW_BUTTON_RIGHT;
    if(k&KEY_DOWN)   b|=GW_BUTTON_DOWN;
    if(k&KEY_A)      b|=GW_BUTTON_A;       /* Jump */
    /* GAME A -> START; TIME -> L; ALARM -> R.
       GAME B (SELECT) does not exist on the YM-105: not assigned. */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* GAME A */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* TIME */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* ALARM */
    return b;
}

const game_desc_t game_smbn = {
    .name = "Super Mario Bros.",
    .rom_path = "/gnw/Super Mario Bros.gnw",
    .cpu = ROM_CPU_SM511,
    .rom_sig = "w_smbn__",
    .dual_screen = 0,          /* single LCD screen (MAIN) */
    .main_uses_top = 0,        /* MAIN shows bottomNS; SUB stays black */
    .use_sm5a = 0,
    .init_screens = NULL,
    .update_buttons = smbn_update_buttons,
};

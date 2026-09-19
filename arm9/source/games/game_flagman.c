/*
 * FLAGMAN (SM5A, single screen).
 * Key mapping per MAME hh_sm510.cpp.
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"

static u32 flagman_update_buttons(void){
    u32 k=keysHeld(), b=0;
    /* 4 actions (corners): real D-pad diagonals + shortcuts. */
    if((k&KEY_UP)    && (k&KEY_LEFT))  b|=GW_BUTTON_UP   | GW_BUTTON_LEFT;  /* up-left */
    if((k&KEY_UP)    && (k&KEY_RIGHT)) b|=GW_BUTTON_UP   | GW_BUTTON_RIGHT; /* up-right */
    if((k&KEY_DOWN)  && (k&KEY_LEFT))  b|=GW_BUTTON_DOWN | GW_BUTTON_LEFT;  /* down-left */
    if((k&KEY_DOWN)  && (k&KEY_RIGHT)) b|=GW_BUTTON_DOWN | GW_BUTTON_RIGHT; /* down-right */
    /* Shortcuts: pure vertical D-pad = left corners. */
    if((k&KEY_UP)    && !(k&KEY_LEFT) && !(k&KEY_RIGHT)) b|=GW_BUTTON_UP   | GW_BUTTON_LEFT;  /* up-left */
    if((k&KEY_DOWN)  && !(k&KEY_LEFT) && !(k&KEY_RIGHT)) b|=GW_BUTTON_DOWN | GW_BUTTON_LEFT;  /* down-left */
    /* Pure horizontal is not a corner (only contributes its direction). */
    if((k&KEY_LEFT)  && !(k&KEY_UP) && !(k&KEY_DOWN)) b|=GW_BUTTON_LEFT;
    if((k&KEY_RIGHT) && !(k&KEY_UP) && !(k&KEY_DOWN)) b|=GW_BUTTON_RIGHT;
    /* Shortcuts X/B = right corners. */
    if(k&KEY_X)      b|=GW_BUTTON_UP   | GW_BUTTON_RIGHT;  /* up-right */
    if(k&KEY_B)      b|=GW_BUTTON_DOWN | GW_BUTTON_RIGHT;  /* down-right */
    /* GAME A -> START, GAME B -> SELECT, TIME -> L, ALARM -> R */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* GAME A */
    if(k&KEY_SELECT) b|=GW_BUTTON_B;      /* GAME B */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* TIME */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* ALARM */
    return b;
}

const game_desc_t game_flagman = {
    .name = "Flagman",
    .rom_path = "/gnw/gnw_flagman.gnw",
    .dual_screen = 0,
    .main_uses_top = 0,
    .use_sm5a = 1,
    .init_screens = NULL,
    .update_buttons = flagman_update_buttons,
};

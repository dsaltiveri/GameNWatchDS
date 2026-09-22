/*
 * SUPER SPARKY (SM510, single screen).
 * Key mapping per MAME hh_sm510.cpp (2 action buttons).
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 super_sparky_update_buttons(void){
    u32 k=keysHeld(), b=0;
    /* 2 action buttons -> D-pad. */
    if(k&KEY_LEFT)   b|=GW_BUTTON_LEFT;
    if(k&KEY_RIGHT)  b|=GW_BUTTON_RIGHT;
    if(k&KEY_A)      b|=GW_BUTTON_A;
    /* GAME A -> START, GAME B -> SELECT, TIME -> L, ALARM -> R */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* GAME A */
    if(k&KEY_SELECT) b|=GW_BUTTON_B;      /* GAME B */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* TIME */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* ALARM */
    return b;
}

/* Color floors per horizontal band (overlay strips): red, blue,
   green, purple (top to bottom). 555. */
static const u16 ssparky_seg_floor[4] = {
    0x905A,  /* band 0 (y 33-50)  (208,23,35) red   */
    0xCDC0,  /* band 1 (y 52-80)  (6,115,153) blue   */
    0xADC2,  /* band 2 (y 83-107) (21,114,93) green  */
    0xC529,  /* band 3 (y 111-191) (75,74,139) purple */
};
/* Y bounds of each band in framebuffer (the backdrop goes to the
   112x192 contain): red 33-50, blue 52-80, green 83-107, purple 111-191. */
static const u16 ssparky_seg_floor_limits[5] = { 33, 51, 82, 110, 192 };

const game_desc_t game_ssparky = {
    .name = "Super Sparky",
    .rom_path = "/gnw/gnw_ssparky.gnw",
    .cpu = ROM_CPU_SM510,
    .rom_sig = "w_sspark",
    .dual_screen = 0,
    .main_uses_top = 0,
    .use_sm5a = 0,
    .seg_floor = ssparky_seg_floor,
    .seg_floor_bands = 4,
    .seg_floor_h = 1,          /* horizontal bands (by row) */
    .seg_floor_y0 = 0,         /* the contain fills the height (192): offset 0 */
    .seg_floor_limits = ssparky_seg_floor_limits,
    .init_screens = NULL,
    .update_buttons = super_sparky_update_buttons,
};

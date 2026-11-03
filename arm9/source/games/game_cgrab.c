/*
 * CRAB GRAB (SM510, single screen).
 * Key mapping per MAME hh_sm510.cpp (2 claw buttons).
 */
#include <nds.h>

#include "emulator.h"
#include "games.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_romloader.h"

static u32 crab_grab_update_buttons(void){
    u32 k=keysHeld(), b=0;
    /* S1 = D-pad (MAME gnw_cgrab INPUT_PORTS):
       K1=RIGHT, K2=UP, K3=LEFT, K4=DOWN. */
    if(k&KEY_LEFT)   b|=GW_BUTTON_LEFT;
    if((k&KEY_X) || (k&KEY_UP))    b|=GW_BUTTON_UP;
    if(k&KEY_RIGHT)  b|=GW_BUTTON_RIGHT;
    if((k&KEY_B) || (k&KEY_DOWN))  b|=GW_BUTTON_DOWN;
    /* S2 = menu: Time, Game B, Game A, Alarm. */
    if(k&KEY_START)  b|=GW_BUTTON_GAME;   /* Game A */
    if(k&KEY_SELECT) b|=GW_BUTTON_B;      /* Game B */
    if((k&KEY_L) && !(k&KEY_R)) b|=GW_BUTTON_TIME;   /* Time */
    if((k&KEY_L) && (k&KEY_R))  b|=GW_BUTTON_ALARM;  /* Alarm */
    return b;
}

/* Color floors per vertical band (strips of the contain in framebuffer):
   purple 77-101, green 102-127, red 128-153, blue 154-179. 555. */
static const u16 cgrab_seg_floor[4] = {
    0xC529,  /* band 0 (x 76-101)  (75,74,138)  purple */
    0xB5A4,  /* band 1 (x 102-127) (33,105,103) green  */
    0xA4D2,  /* band 2 (x 128-153) (143,51,73)  red   */
    0xCDC1,  /* band 3 (x 154-179) (6,114,152)  blue   */
};
/* X bounds of each band in framebuffer (contain x=77..179):
   purple 77-101, green 102-127, red 128-153, blue 154-179. */
static const u16 cgrab_seg_floor_limits[5] = { 77, 102, 128, 154, 180 };

const game_desc_t game_cgrab = {
    .name = "Crab Grab",
    .rom_path = "/gnw/Crab Grab.gnw",
    .cpu = ROM_CPU_SM510,
    .rom_sig = "w_cgrab_",
    .dual_screen = 0,
    .main_uses_top = 0,
    .use_sm5a = 0,
    .seg_floor = cgrab_seg_floor,
    .seg_floor_bands = 4,
    .seg_floor_limits = cgrab_seg_floor_limits,   /* bands by column (fx) */
    .seg_floor_y0 = 21,      /* where the vertical strips start (uniform zone on top) */
    .init_screens = NULL,
    .update_buttons = crab_grab_update_buttons,
};

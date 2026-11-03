/*
 * Unified G&W emulator for Nintendo DS (GameNWatchDS).
 * Common LCD rendering core (direct 16bpp BG3 updates), odometer-paced audio
 * and the main loop, parameterized per game through game_desc_t.
 */
#ifndef _EMULATOR_H_
#define _EMULATOR_H_

#include "gw_sys/gw_type_defs.h"

/* DS framebuffer size (2 screens of 256x192). */
#define FBW 256
#define FBH 192

/* Description of a game: everything that varies between the supported G&W
   units. ROM, segments and backgrounds are loaded from the .gnw file on the
   SD card. */
typedef struct game_desc {
    const char *name;                 /* name shown in the menu */
    const char *rom_path;             /* SD path of the .gnw (e.g. "/gnw/Fire.gnw") */

    /* Identity written in the .gnw header, used to recognise the file when it
       is opened from a loader (TWiLight Menu++) and it is not in /gnw/ or has
       been renamed. Both are fixed 8-byte strings in the header. */
    const char *cpu;                  /* CPU name (ROM_CPU_* in gw_sys/gw_romloader.h) */
    const char *rom_sig;              /* ROM signature (e.g. "w_dkong2") */

    /* Behaviour flags */
    int dual_screen;     /* 1 = two LCD screens; 0 = single (MAIN only) */
    int main_uses_top;   /* 1 = MAIN shows topNS; 0 = MAIN shows bottomNS */
    int use_sm5a;        /* 1 = SM5A/SM500 rendering via O/W outputs */
    int lcd_inverted;    /* 1 = inverted LCD (Panorama/Tabletop): black
                            background and segments show the artwork in color */
    const u16 *seg_floor;    /* array of 555 (Bmp16) floor colors per band,
                               used as an overlay tint on lit segments */
    u8  seg_floor_bands;     /* number of vertical bands (width 256/bands); 0 = none */    int seg_floor_x0;        /* starting X column of the LCD (bands relative to it) */
    int seg_floor_band_w;    /* width of each band (px); 0 = divide the full width */    int seg_floor_y0;        /* first Y row where the overlay starts (floor); 0 = whole */    int seg_floor_h;         /* 1 = horizontal bands (by row); 0 = vertical (by column) */    const u16 *seg_floor_limits; /* non-uniform bands: bands+1 Y bounds (seg_floor_h only); NULL = uniform band_w */

    /* Game-specific hooks */
    void (*init_screens)(void);    /* reserved */
    u32  (*update_buttons)(void);  /* per-game key assignment */
} game_desc_t;

/* Current G&W button state (written by the loop, read by gw_system). */
extern u32 gw_buttons_state;

/* Runs the game in an infinite loop. Returns 1 when the player presses
   L+R to go back to the main menu. */
int emulator_run(const game_desc_t *g);

/* Same as emulator_run() but reading the .gnw from an explicit path: used when
   the loader (TWiLight Menu++, .argv files...) opens the game directly, so the
   file may live outside /gnw/. rom_path == NULL keeps g->rom_path. */
int emulator_run_path(const game_desc_t *g, const char *rom_path);

#endif /* _EMULATOR_H_ */


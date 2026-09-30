/*
 * Port of the LCD Game Emulator (https://github.com/bzhxx/lcd_game_emulator)
 * Original author: bzhxx — GPLv3 license.
 * Nintendo DS adaptation.
 */
#ifndef _GW_ROMLOADER_H_
#define _GW_ROMLOADER_H_

/* Different 4-bit SHARP CPUs. */
#define ROM_CPU_SM5A  "SM5A_"
#define ROM_CPU_SM500 "SM500"
#define ROM_CPU_SM510 "SM510"
#define ROM_CPU_SM511 "SM511"
#define ROM_CPU_SM512 "SM512"
#define ROM_CPU_SM520 "SM520"
#define ROM_CPU_SM530 "SM530"

/* flags in the ROM file */
#define FLAG_RENDERING_LCD_INVERTED 0x01
#define FLAG_SEGMENTS_4BITS         0x10
#define FLAG_SEGMENTS_2BITS         0x100
#define FLAG_BACKGROUND_JPEG        0x20

/* Piezo buzzer mode (bits 1..3 of rom_head.flags). */
#define FLAG_SOUND_MASK 0xE
#define FLAG_SOUND_R1_PIEZO   (1 << 1)
#define FLAG_SOUND_R2_PIEZO   (2 << 1)
#define FLAG_SOUND_R1R2_PIEZO (3 << 1)
#define FLAG_SOUND_R1S1_PIEZO (4 << 1)
#define FLAG_SOUND_S1R1_PIEZO (5 << 1)

/* LCD deflicker mode (bits 6..7 of rom_head.flags). */
#define FLAG_LCD_DEFLICKER_MASK 0xC0
#define FLAG_LCD_DEFLICKER_OFF  0x00
#define FLAG_LCD_DEFLICKER_1    0x40
#define FLAG_LCD_DEFLICKER_2    0x80
#define FLAG_LCD_DEFLICKER_3    0xC0

/* Pointers to the ROM objects (embedded in rom_data.s). */
extern unsigned char  *gw_segments;
extern unsigned short *gw_segments_x;
extern unsigned short *gw_segments_y;
extern unsigned short *gw_segments_width;
extern unsigned short *gw_segments_height;
extern unsigned int   *gw_segments_offset;
extern unsigned char  *gw_program;
extern unsigned char  *gw_melody;
extern unsigned int   *gw_keyboard;

/* ROM header. */
typedef struct gwromheader_s
{
   char cpu_name[8];               /* SHARP CPU to emulate */
   char rom_signature[8];          /* last 8 characters of the ROM name */

   unsigned int flags;             /* buzzer and deflicker */

   unsigned int background_pixel;      /* unused on DS (backdrop via grit) */
   unsigned int background_pixel_size;

   unsigned int segments_pixel;
   unsigned int segments_pixel_size;

   unsigned int segments_offset;       /* segment offset and dimensions */
   unsigned int segments_offset_size;
   unsigned int segments_x;
   unsigned int segments_x_size;
   unsigned int segments_y;
   unsigned int segments_y_size;
   unsigned int segments_height;
   unsigned int segments_height_size;
   unsigned int segments_width;
   unsigned int segments_width_size;

   unsigned int melody;                /* melody */
   unsigned int melody_size;

   unsigned int program;               /* CPU program */
   unsigned int program_size;

   unsigned int keyboard;              /* keyboard mapping */
   unsigned int keyboard_size;
} gwromheader_t;

extern gwromheader_t gw_head;

/* Maximum size of a .gnw loaded from SD (program + geometry + keyboard
   + 2 RGB565 backdrops). Current packages peak around 235 KiB. */
#define GW_ROM_MAX_SIZE (256 * 1024)

/* RGB565 backdrops packed inside the .gnw (background_pixel object). */
#define GW_BACKDROP_SIZE (256 * 192 * 2)  /* 98304 bytes: 256x192 at 16bpp */
#define GW_BACKDROPS 2                    /* [0] = topNS, [1] = bottomNS */

/* Loads the .gnw ROM of a given game (pointer and size). */
bool gw_romloader_load(const unsigned char *rom, unsigned int rom_size);

/* Reads a .gnw from the SD card (e.g. "/gnw/gnw_dkong2.gnw") and processes it. */
bool gw_romloader_load_file(const char *path);

/* Returns the indexed backdrop of the loaded .gnw (0 = topNS, 1 = bottomNS),
   or NULL if the .gnw includes no backdrops. */
const unsigned char *gw_rom_backdrop(int index);

/* Loads (or reloads) the active ROM of the current game. */
bool gw_romloader();

#endif /* _GW_ROMLOADER_H_ */

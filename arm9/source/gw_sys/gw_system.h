/*
 * Port of the LCD Game Emulator (https://github.com/bzhxx/lcd_game_emulator)
 * Original author: bzhxx — GPLv3 license.
 * Nintendo DS adaptation.
 */
#ifndef _GW_SYSTEM_H_
#define _GW_SYSTEM_H_

#include "gw_type_defs.h"

/* System clock = Audio clock = 32768Hz */
#define GW_SYS_FREQ 32768U
#define GW_AUDIO_FREQ GW_SYS_FREQ

/* Refresh rate (Hz) and CPU cycles per frame. */
#define GW_REFRESH_RATE 60

/* Audio samples per frame. */
#define GW_AUDIO_BUFFER_LENGTH (GW_AUDIO_FREQ / GW_REFRESH_RATE)

/* Emulated system : number of clock cycles per loop */
#define GW_SYSTEM_CYCLES (GW_AUDIO_FREQ / GW_REFRESH_RATE)

/* Main API to emulate the system */

// Configure, start and reset (in this order)
bool gw_system_config();
void gw_system_start();
void gw_system_reset();

// Run some clock cycles
int gw_system_run(int clock_cycles);

// Audio init
void gw_system_sound_init();

// ROM loader
bool gw_system_romload();

// get buttons state
unsigned int gw_get_buttons();

/* shared audio buffer between host and emulator */
extern unsigned char gw_audio_buffer[GW_AUDIO_BUFFER_LENGTH];

#ifdef HARNESS_DEBUG
/* Debug for the PC harness: histogram of K reads (io_S, io_K). */
extern long gw_readk_count[256][16];
#endif

/* Output of emulated system  */
void gw_writeR(unsigned char data);

/* Input of emulated system */
unsigned char gw_readK(unsigned char S);
unsigned char gw_readBA();
unsigned char gw_readB();

#define GW_BUTTON_LEFT 1
#define GW_BUTTON_UP (1 << 1)
#define GW_BUTTON_RIGHT (1 << 2)
#define GW_BUTTON_DOWN (1 << 3)
#define GW_BUTTON_A (1 << 4)
#define GW_BUTTON_B (1 << 5)
#define GW_BUTTON_TIME (1 << 6)
#define GW_BUTTON_GAME (1 << 7)

/* Soft alarm key: bit 11 of gw_get_buttons(). */
#define GW_BUTTON_ALARM (1 << 11)

#define GW_MASK_K1 0x000000ff
#define GW_MASK_K2 0x0000ff00
#define GW_MASK_K3 0x00ff0000
#define GW_MASK_K4 0xff000000

#endif /* _GW_SYSTEM_H_ */
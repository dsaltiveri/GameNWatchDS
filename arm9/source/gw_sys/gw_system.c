/*
 * Port of the LCD Game Emulator (https://github.com/bzhxx/lcd_game_emulator)
 * Original author: bzhxx — GPLv3 license.
 * Nintendo DS adaptation: PWM audio, keyboard and system functions.
 */
#include <stdbool.h>
#include <string.h>

#include "sm510.h"
#include "sm500.h"
#include "gw_romloader.h"
#include "gw_system.h"
#include "gw_graphic.h"

static void (*device_reset)();
static void (*device_start)();
static void (*device_run)();

static unsigned char previous_dpad;
static bool gw_keyboard_multikey[8];

/* The FR-27 (SM5A) K-port filter applies ONLY to fire: on SM510/511 the
   firmware sweeps every R/S row for K. Detected in gw_system_config() from
   the CPU name of the loaded ROM. */
static bool is_sm5a_keyboard = false;

/* map functions and custom configuration */
bool gw_system_config()
{
	/* init graphics parameters (deflicker) */
	gw_gfx_init();

	/* The FR-27 (fire) K-port filter is specific to that game: its SM5A only
	   has a keyboard on row R4 (bit 3 of io_S). Other SM5A games (ball, chef,
	   etc.) sweep all S rows, so the filter must not be applied there. */
	is_sm5a_keyboard = (strncmp(gw_head.rom_signature, "w_fire__", 8) == 0);

	/* Detect DPAD multi-key mode (diagonal combos) for each S line. */
	for (int i = 0; i < 8; i++)
	{
		gw_keyboard_multikey[i] = false;

		un32 score = 0;
		un8 K1 = gw_keyboard[i] & 0xFF;
		un8 K2 = (gw_keyboard[i] >> 8) & 0xFF;
		un8 K3 = (gw_keyboard[i] >> 16) & 0xFF;
		un8 K4 = (gw_keyboard[i] >> 24) & 0xFF;

		un8 C1 = GW_BUTTON_LEFT + GW_BUTTON_UP;
		un8 C2 = GW_BUTTON_LEFT + GW_BUTTON_DOWN;
		un8 C3 = GW_BUTTON_RIGHT + GW_BUTTON_UP;
		un8 C4 = GW_BUTTON_RIGHT + GW_BUTTON_DOWN;

		for (int c = 0; c < 4; c++)
		{
			un8 comb = (c == 0) ? C1 : (c == 1) ? C2 : (c == 2) ? C3 : C4;
			if (K1 == comb) score++;
			else if (K2 == comb) score++;
			else if (K3 == comb) score++;
			else if (K4 == comb) score++;
		}

		if (score == 4)
			gw_keyboard_multikey[i] = true;
	}

	previous_dpad = 0;

	/* Select CPU implementation by ROM header name. */
	if (strncmp(gw_head.cpu_name, ROM_CPU_SM500, 5) == 0)
	{
		device_reset = sm500_device_reset;
		device_start = sm500_device_start;
		device_run = sm500_execute_run;
		return true;
	}

	if (strncmp(gw_head.cpu_name, ROM_CPU_SM5A, 5) == 0)
	{
		device_start = sm5a_device_start;
		device_reset = sm5a_device_reset;
		device_run = sm5a_execute_run;
		return true;
	}

	if (strncmp(gw_head.cpu_name, ROM_CPU_SM510, 5) == 0)
	{
		device_start = sm510_device_start;
		device_reset = sm510_device_reset;
		device_run = sm510_execute_run;
		return true;
	}

	if (strncmp(gw_head.cpu_name, ROM_CPU_SM511, 5) == 0)
	{
		device_start = sm510_device_start;
		device_reset = sm511_device_reset;
		device_run = sm511_execute_run;
		return (sm511_init_melody(gw_melody));
	}

	if (strncmp(gw_head.cpu_name, ROM_CPU_SM512, 5) == 0)
	{
		device_start = sm510_device_start;
		device_reset = sm511_device_reset;
		device_run = sm511_execute_run;
		return (sm511_init_melody(gw_melody));
	}

	return false;
}

void gw_system_reset() { device_reset(); }
void gw_system_start() { device_start(); }
bool gw_system_romload() { return gw_romloader(); }

/******** Audio functions *******************/
static unsigned char mspeaker_data = 0;
static int gw_audio_buffer_idx = 0;
/* Fractional remainder accumulator for the cycle divider (see
   gw_system_run). Reset in gw_system_sound_init() when each game starts. */
static unsigned int audio_cycle_rem = 0;

/* Audio buffer */
/* Per-frame audio buffer (SM511 fills 544 of 546; the rest is padded). */
unsigned char gw_audio_buffer[GW_AUDIO_BUFFER_LENGTH];

#ifdef HARNESS_DEBUG
/* Debug for the PC harness: histogram of K reads (io_S, io_K). Only built
   with -DHARNESS_DEBUG (tools/_harness); on the DS it costs nothing. */
long gw_readk_count[256][16];
#endif

void gw_system_sound_init()
{
	memset(gw_audio_buffer, 0, sizeof(gw_audio_buffer));
	gw_audio_buffer_idx = 0;
	mspeaker_data = 0;
	audio_cycle_rem = 0; /* clean fractional remainder for the new game */
}

static void gw_system_sound_melody(unsigned char data)
{
	/* SM511: R pin is the melody output. */
	if (gw_melody != 0)
		mspeaker_data = data;
	else
	{
		switch (gw_head.flags & FLAG_SOUND_MASK)
		{
		case FLAG_SOUND_R2_PIEZO:
			mspeaker_data = (data >> 1) & 1;
			break;
		case FLAG_SOUND_R1R2_PIEZO:
			mspeaker_data = data & 3;
			break;
		case FLAG_SOUND_R1S1_PIEZO:
			mspeaker_data = (m_s_out & ~1) | (data & 1);
			break;
		case FLAG_SOUND_S1R1_PIEZO:
			mspeaker_data = (m_s_out & ~2) | ((data << 1) & 2);
			break;
		case FLAG_SOUND_R1_PIEZO:
		default:
			mspeaker_data = data & 1;
			break;
		}
	}

	if (gw_audio_buffer_idx < (int)sizeof(gw_audio_buffer))
		gw_audio_buffer[gw_audio_buffer_idx++] = mspeaker_data;
}

void gw_writeR(unsigned char data) { gw_system_sound_melody(data); }

/******** Keys functions **********************/
/* gw_get_buttons() bits: left | up<<1 | right<<2 | down<<3 |
   a<<4 | b<<5 | time<<6 | game<<7 | pause<<8 | power<<9. */

/* Default value is 1 (pull-up). */
unsigned char gw_readB()
{
	unsigned int keys_pressed = gw_get_buttons() & 0xff;
	if (keys_pressed == 0)
		return 1;
	return (gw_keyboard[9] & keys_pressed) ? 0 : 1;
}

/* Default value is 1 (pull-up). */
unsigned char gw_readBA()
{
	unsigned int keys_pressed = gw_get_buttons() & 0xff;
	if (keys_pressed == 0)
		return 1;
	return (gw_keyboard[8] & keys_pressed) ? 0 : 1;
}

/* Default value is 0 (pull-down). */
unsigned char gw_readK(unsigned char io_S)
{
	unsigned char io_K = 0;
	static unsigned int dpad_shortcut_diagonal_pressed = 0;
	static unsigned int dpad_shortcut_diagonal_hold = 0;

	unsigned int gw_buttons = gw_get_buttons();

	/* K port of the FR-27 (SM5A, fire): only row R4 (bit 3 of io_S) carries
	   the Time/GameB/GameA/Alarm buttons. The other rows have no user keyboard:
	   returning 0 prevents the soft matrix from returning stray K bits and
	   triggering the hidden factory routines (reset/LCD test) when pressing
	   Game A or Alarm. On SM510/511 the sweep uses every row, so this filter
	   does NOT apply there (is_sm5a_keyboard == false). */
	if (is_sm5a_keyboard)
	{
		if ((io_S & 0x8) == 0)
			return 0;

		/* ALARM: bit 3 of the K port, already inside the R4-row filter.
		   Bit 0x8 of rows R2/R3 is a factory test ("alarm test?") that shares
		   code with Game B: it must NOT be returned here. */
		if (gw_buttons & GW_BUTTON_ALARM)
			return 0x8;
	}

	unsigned int keys_pressed = gw_buttons & 0xff;
	unsigned int key_soft_value = 0;

	const unsigned int KEY_SOFT_TIME = GW_BUTTON_B + GW_BUTTON_TIME;
	const unsigned int KEY_SOFT_ALARM = GW_BUTTON_B + GW_BUTTON_GAME;

	/* Soft keys: bit 10 = TIME, bit 11 = ALARM. */
	if ((gw_buttons >> 10) & 1)
	{
		keys_pressed = 0;
		key_soft_value = KEY_SOFT_TIME;
	}
	if ((gw_buttons >> 11) & 1)
	{
		keys_pressed = 0;
		key_soft_value = KEY_SOFT_ALARM;
	}
	if (keys_pressed == KEY_SOFT_ALARM)
	{
		key_soft_value = KEY_SOFT_ALARM;
		keys_pressed = 0;
	}
	if (keys_pressed == KEY_SOFT_TIME)
	{
		key_soft_value = KEY_SOFT_TIME;
		keys_pressed = 0;
	}

	/* Monitor A button as diagonal shortcut when pressed. */
	if (keys_pressed & GW_BUTTON_A)
		dpad_shortcut_diagonal_pressed = 1;
	if ((keys_pressed & GW_BUTTON_A) == 0)
	{
		dpad_shortcut_diagonal_hold = 0;
		dpad_shortcut_diagonal_pressed = 0;
	}

	if (keys_pressed == 0 && key_soft_value == 0)
		return 0;

	for (int Sx = 0; Sx < 8; Sx++)
	{
		/* R/S output is not used to poll buttons (R2/S2 config). */
		if (io_S == 0)
			io_S = 2;

		if (((io_S >> Sx) & 0x1) != 0)
		{
			if (gw_keyboard_multikey[Sx])
			{
				/* DPAD multi-key with relative change and shortcut. */
				keys_pressed &= (GW_BUTTON_LEFT + GW_BUTTON_RIGHT +
						 GW_BUTTON_UP + GW_BUTTON_DOWN);

				if (dpad_shortcut_diagonal_pressed == 1 &&
				    dpad_shortcut_diagonal_hold == 0)
				{
					dpad_shortcut_diagonal_hold = 1;
					keys_pressed = ~previous_dpad &
						(GW_BUTTON_LEFT + GW_BUTTON_RIGHT +
						 GW_BUTTON_UP + GW_BUTTON_DOWN);
				}

				if (keys_pressed == GW_BUTTON_LEFT)
					keys_pressed = (previous_dpad & (GW_BUTTON_UP + GW_BUTTON_DOWN)) | GW_BUTTON_LEFT;
				if (keys_pressed == GW_BUTTON_RIGHT)
					keys_pressed = (previous_dpad & (GW_BUTTON_UP + GW_BUTTON_DOWN)) | GW_BUTTON_RIGHT;
				if (keys_pressed == GW_BUTTON_DOWN)
					keys_pressed = (previous_dpad & (GW_BUTTON_LEFT + GW_BUTTON_RIGHT)) | GW_BUTTON_DOWN;
				if (keys_pressed == GW_BUTTON_UP)
					keys_pressed = (previous_dpad & (GW_BUTTON_LEFT + GW_BUTTON_RIGHT)) | GW_BUTTON_UP;

				if ((gw_keyboard[Sx] & GW_MASK_K1) == keys_pressed)
				{
					io_K |= 0x1;
					previous_dpad = keys_pressed;
				}
				if ((gw_keyboard[Sx] & GW_MASK_K2) == (keys_pressed << 8))
				{
					io_K |= 0x2;
					previous_dpad = keys_pressed;
				}
				if ((gw_keyboard[Sx] & GW_MASK_K3) == (keys_pressed << 16))
				{
					io_K |= 0x4;
					previous_dpad = keys_pressed;
				}
				if ((gw_keyboard[Sx] & GW_MASK_K4) == (keys_pressed << 24))
				{
					io_K |= 0x8;
					previous_dpad = keys_pressed;
				}
			}
			else
			{
				/* Soft keys take precedence. */
				if (key_soft_value != 0)
				{
					if ((gw_keyboard[Sx] & GW_MASK_K1) == key_soft_value)
						io_K |= 0x1;
					if ((gw_keyboard[Sx] & GW_MASK_K2) == (key_soft_value << 8))
						io_K |= 0x2;
					if ((gw_keyboard[Sx] & GW_MASK_K3) == (key_soft_value << 16))
						io_K |= 0x4;
					if ((gw_keyboard[Sx] & GW_MASK_K4) == (key_soft_value << 24))
						io_K |= 0x8;
				}
				else
				{
					if (((gw_keyboard[Sx] & GW_MASK_K1) & keys_pressed) != 0)
						if ((gw_keyboard[Sx] & GW_MASK_K1) != KEY_SOFT_ALARM &&
						    (gw_keyboard[Sx] & GW_MASK_K1) != KEY_SOFT_TIME)
							io_K |= 0x1;
					if (((gw_keyboard[Sx] & GW_MASK_K2) & (keys_pressed << 8)) != 0)
						if ((gw_keyboard[Sx] & GW_MASK_K2) != (KEY_SOFT_ALARM << 8) &&
						    (gw_keyboard[Sx] & GW_MASK_K2) != (KEY_SOFT_TIME << 8))
							io_K |= 0x2;
					if (((gw_keyboard[Sx] & GW_MASK_K3) & (keys_pressed << 16)) != 0)
						if ((gw_keyboard[Sx] & GW_MASK_K3) != (KEY_SOFT_ALARM << 16) &&
						    (gw_keyboard[Sx] & GW_MASK_K3) != (KEY_SOFT_TIME << 16))
							io_K |= 0x4;
					if (((gw_keyboard[Sx] & GW_MASK_K4) & (keys_pressed << 24)) != 0)
						if ((gw_keyboard[Sx] & GW_MASK_K4) != (KEY_SOFT_ALARM << 24) &&
						    (gw_keyboard[Sx] & GW_MASK_K4) != (KEY_SOFT_TIME << 24))
							io_K |= 0x8;
				}
			}
		}
	}

#ifdef HARNESS_DEBUG
	gw_readk_count[io_S & 0xff][io_K & 0x0f]++;
#endif
	return io_K & 0xf;
}

int gw_system_run(int clock_cycles)
{
	gw_audio_buffer_idx = 0;

	/* Check if a key is pressed to wake up the system. */
	m_k_active = (gw_get_buttons() != 0);

	/* 1 CPU operation in m_clk_div clock cycles.
	   SM510/SM5A: 2 cycles/op (2×273=546 exact -> fills all 546 samples).
	   SM511/SM512: 4 cycles/op (546 is not divisible by 4 -> 544 samples
	   plus 2 garbage bytes at the end of the buffer = noise/crackle).
	   The fractional remainder is accumulated to spend fair cycles and the
	   buffer is padded up to GW_AUDIO_BUFFER_LENGTH to avoid that garbage. */
	unsigned int total = (unsigned int)clock_cycles + audio_cycle_rem;
	m_icount += total / (unsigned int)m_clk_div;
	audio_cycle_rem = total % (unsigned int)m_clk_div;

	device_run();

	/* Fill the buffer if the SM511 did not fill it completely: the missing
	   samples are stable data (last melody value). */
	while (gw_audio_buffer_idx < GW_AUDIO_BUFFER_LENGTH) {
        unsigned char last = gw_audio_buffer_idx ? gw_audio_buffer[gw_audio_buffer_idx-1] : 0;
        gw_audio_buffer[gw_audio_buffer_idx++] = last;
    }

	/* Return cycles really executed according to divider. */
	return m_icount * m_clk_div;
}

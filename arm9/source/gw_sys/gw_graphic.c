/*
 * Port of the LCD Game Emulator (https://github.com/bzhxx/lcd_game_emulator)
 * Original author: bzhxx — GPLv3 license.
 * Nintendo DS adaptation: segment state computation only.
 */
#include <string.h>

#include "gw_type_defs.h"
#include "sm510.h"
#include "sm500.h"
#include "gw_graphic.h"
#include "gw_system.h"
#include "gw_romloader.h"

/* Flicker filter enable flag */
static bool deflicker_enabled = false;

void gw_gfx_init()
{
	/* init LCD deflicker level */
	flag_lcd_deflicker_level = (gw_head.flags & FLAG_LCD_DEFLICKER_MASK) >> 6;
	deflicker_enabled = (flag_lcd_deflicker_level != 0);
}

/*
   Computes the final ON/OFF state of each LCD segment (256 entries).
   SM510/SM511 layout:
     segment_position = 4*y + z  (A/B/C groups: b at +64, c at +192)
     bs1/bs2: 128+z and 132+z.
   The deflicker (gw_ram_state) is resolved here, before the consumer
   reads the result, so a plain OR of active pixels is correct.
*/
void gw_calc_segment_states(unsigned char seg_on[256])
{
	uint8 HxA, HxB, HxC; // RAM segment 4bits value H4..H1
	uint8 segment_position;
	uint8 segment_state;

	memset(seg_on, 0, 256);

	for (int seg_y = 0; seg_y < NB_SEGS_ROW; seg_y++)
	{
		if (deflicker_enabled)
		{
			HxA = gw_ram_state[ADD_SEGA_BASE + seg_y] & 0xf;
			HxB = gw_ram_state[ADD_SEGB_BASE + seg_y] & 0xf;
			HxC = gw_ram_state[ADD_SEGC_BASE + seg_y] & 0xf;
		}
		else
		{
			HxA = gw_ram[ADD_SEGA_BASE + seg_y] & 0xf;
			HxB = gw_ram[ADD_SEGB_BASE + seg_y] & 0xf;
			HxC = gw_ram[ADD_SEGC_BASE + seg_y] & 0xf;
		}

		for (int seg_z = 0; seg_z < NB_SEGS_COL; seg_z++)
		{
			segment_position = 4 * seg_y + seg_z;

			// segment a
			segment_state = m_bc || !m_bp ? 0 : (HxA & (1 << seg_z)) != 0;
			seg_on[segment_position] = segment_state;

			// segment b
			segment_state = m_bc || !m_bp ? 0 : (HxB & (1 << seg_z)) != 0;
			seg_on[segment_position + 64] = segment_state;

			// segment c
			segment_state = m_bc || !m_bp ? 0 : (HxC & (1 << seg_z)) != 0;
			seg_on[segment_position + 192] = segment_state;
		}
	}

	/* bs1,bs2 output from L/X and Y regs */
	for (int seg_z = 0; seg_z < NB_SEGS_COL; seg_z++)
	{
		/* Blinking mask using m_y and m_div as timer */
		uint8 blink = (m_div & 0x4000) ? m_y : 0;

		/* bs1 is derived from ml */
		uint8 seg = (m_l & ~blink);
		segment_state = (m_bc || !m_bp) ? 0 : seg;
		seg_on[128 + seg_z] = ((segment_state & (1 << seg_z)) != 0);

		/* bs2 is derived from mx */
		seg = (m_x & ~blink);
		segment_state = (m_bc || !m_bp) ? 0 : seg;
		seg_on[132 + seg_z] = ((segment_state & (1 << seg_z)) != 0);
	}
}

/*
   SM5A/SM500 variant (Game & Watch Fire, FR-27).
   SAME SOLUTION as LCD-Game-Emulator (gw_gfx_sm500_rendering):
     slot = 8*a + 2*b + c  (a: O group, b: bit, c: latch 0=W/1=W')

   Latch states are updated by the firmware itself at the program's
   STABLE POINTS: sm500_op_kta(), sm500_op_tal(), sm500_op_tb() and
   sm500_op_rtn0() (if deflicker level<2) via
   sm500_update_segments_state().

   With the deflicker FLAGS enabled (level 1), the renderer ALWAYS
   reads m_o_state/m_ox_state: intermediate states are never drawn,
   DTW/TW/PTW transfers (no ghost segments) and motion are updated
   each time the firmware polls (smooth).
*/
void gw_calc_segment_states_sm5a(unsigned char seg_on[256])
{
	memset(seg_on, 0, 256);

	u8 seg;

	/* Faithful to the original renderer gw_gfx_sm500_rendering from
	   LCD-Game-Emulator: when deflicker is active the "frozen" _state
	   latches (m_o_state/m_ox_state) are read; the firmware only updates
	   them at the stable KTA/TAL/TB/RTN points via
	   sm500_update_segments_state(); with deflicker OFF the live
	   latches m_o/m_ox are read. */
	for (int h = 0; h < 2; h++)
	{
		for (int o = 0; o < m_o_pins; o++)
		{
			if (deflicker_enabled)
				seg = h ? m_ox_state[o] : m_o_state[o];
			else
				seg = h ? m_ox[o] : m_o[o];

			seg_on[8 * o + 0 + h] = m_bp ? ((seg & 0x1) != 0) : 0;
			seg_on[8 * o + 2 + h] = m_bp ? ((seg & 0x2) != 0) : 0;
			seg_on[8 * o + 4 + h] = m_bp ? ((seg & 0x4) != 0) : 0;
			seg_on[8 * o + 6 + h] = m_bp ? ((seg & 0x8) != 0) : 0;
		}
	}
}

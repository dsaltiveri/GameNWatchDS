/*
 * Port of the LCD Game Emulator (https://github.com/bzhxx/lcd_game_emulator)
 * Original author: bzhxx — GPLv3 license.
 * Nintendo DS adaptation.
 */
#ifndef _GW_GRAPHIC_H_
#define _GW_GRAPHIC_H_

/****************************/
// H1..4
#define NB_SEGS_COL 4
// a1...a16
#define NB_SEGS_ROW 16
// a,b,c base addresses
#define ADD_SEGA_BASE 0x60
#define ADD_SEGB_BASE 0x70
#define ADD_SEGC_BASE 0x50

void gw_gfx_init();

/* Computes the final ON/OFF (0/1) state of each LCD segment (256 entries).
   Handles deflicker (gw_ram_state) and the A/B/C layout + bs1/bs2.
   Called once per emulated frame. (CPU SM511/SM512/SM510) */
void gw_calc_segment_states(unsigned char seg_on[256]);

/* Variant for SM5A/SM500 CPUs: segments are driven by the O outputs
   (9 x 4 bits) through two latches: W (m_o_state, slots 0..35) and
   W' (m_ox_state, slots 36..71). */
void gw_calc_segment_states_sm5a(unsigned char seg_on[256]);

#endif /* _GW_GRAPHIC_H_ */
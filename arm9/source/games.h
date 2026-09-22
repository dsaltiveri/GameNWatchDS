/*
 * Game catalog for the emulator: each entry describes a Game & Watch
 * with its ROM, backdrops and specific behavior (keys, screen layout...).
 */
#ifndef _GAMES_H_
#define _GAMES_H_

#include "emulator.h"

extern const game_desc_t game_ball;
extern const game_desc_t game_fires;
extern const game_desc_t game_vermin;
extern const game_desc_t game_helmet;
extern const game_desc_t game_octopus;
extern const game_desc_t game_pchute;
extern const game_desc_t game_popeye;
extern const game_desc_t game_chef;
extern const game_desc_t game_egg;
extern const game_desc_t game_flagman;
extern const game_desc_t game_judge;
extern const game_desc_t game_lion;
extern const game_desc_t game_manholeg;
extern const game_desc_t game_mmouse;
extern const game_desc_t game_dkjr;
extern const game_desc_t game_dkjrp;
extern const game_desc_t game_dkcirc;
extern const game_desc_t game_fireatk;
extern const game_desc_t game_manhole;
extern const game_desc_t game_mariocm;
extern const game_desc_t game_mariocmt;
extern const game_desc_t game_stennis;
extern const game_desc_t game_snoopyp;
extern const game_desc_t game_tbridge;
extern const game_desc_t game_tfish;
extern const game_desc_t game_bfightn;
extern const game_desc_t game_climbern;
extern const game_desc_t game_mariotj;
extern const game_desc_t game_mbaway;
extern const game_desc_t game_dkong;
extern const game_desc_t game_ghouse;
extern const game_desc_t game_opanic;
extern const game_desc_t game_squish;
extern const game_desc_t game_bjack;
extern const game_desc_t game_bsweep;
extern const game_desc_t game_gcliff;
extern const game_desc_t game_pinball;
extern const game_desc_t game_sbuster;
extern const game_desc_t game_zelda;
extern const game_desc_t game_mario;
extern const game_desc_t game_rshower;
extern const game_desc_t game_dkong2;
extern const game_desc_t game_fire;
extern const game_desc_t game_lboat;
extern const game_desc_t game_mickdon;
extern const game_desc_t game_smbn;
extern const game_desc_t game_popeyep;
extern const game_desc_t game_mmousep;
extern const game_desc_t game_bfight;
extern const game_desc_t game_boxing;
extern const game_desc_t game_cgrab;
extern const game_desc_t game_climber;
extern const game_desc_t game_dkhockey;
extern const game_desc_t game_dkong3;
extern const game_desc_t game_smb;
extern const game_desc_t game_ssparky;

extern const game_desc_t *const games[];
extern const int game_count;

/* Looks up a descriptor by the file name of a .gnw, no matter the folder or the
   device it is opened from ("sd:/roms/gnw/gnw_dkong.gnw" matches the catalog
   entry "/gnw/gnw_dkong.gnw"), case-insensitive. NULL if it is not a known
   .gnw. */
const game_desc_t *games_find_by_file(const char *path);

/* Looks up a descriptor by the CPU name and the 8-byte ROM signature stored in
   the .gnw header (e.g. "SM510" + "w_dkong2"), which is how a renamed .gnw is
   recognised. The pair (not the signature alone) tells apart the games sharing
   a signature: Popeye, Manhole, Mario... NULL when unknown. */
const game_desc_t *games_find_by_rom(const char *cpu_name, const char *rom_sig);

#endif /* _GAMES_H_ */

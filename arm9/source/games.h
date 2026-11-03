/*
 * Game catalog for the emulator: each entry describes a Game & Watch
 * with its ROM, backdrops and specific behavior (keys, screen layout...).
 */
#ifndef _GAMES_H_
#define _GAMES_H_

#include "emulator.h"

#include "game_catalog.h"

#define GAME_DECLARE(name) extern const game_desc_t game_##name;
GAME_CATALOG(GAME_DECLARE)
#undef GAME_DECLARE

#define GAME_COUNT_ENTRY(name) + 1
enum { GAME_COUNT = 0 GAME_CATALOG(GAME_COUNT_ENTRY) };
#undef GAME_COUNT_ENTRY

extern const game_desc_t *const games[GAME_COUNT];
extern const int game_count;

/* Looks up a descriptor by the file name of a .gnw, no matter the folder or the
   device it is opened from ("sd:/roms/gnw/Donkey Kong.gnw" matches the catalog
   entry "/gnw/Donkey Kong.gnw"), case-insensitive. NULL if it is not a known
   .gnw. */
const game_desc_t *games_find_by_file(const char *path);

/* Looks up a descriptor by the CPU name and the 8-byte ROM signature stored in
   the .gnw header (e.g. "SM510" + "w_dkong2"), which is how a renamed .gnw is
   recognised. The pair (not the signature alone) tells apart the games sharing
   a signature: Popeye, Manhole, Mario... NULL when unknown. */
const game_desc_t *games_find_by_rom(const char *cpu_name, const char *rom_sig);

#endif /* _GAMES_H_ */


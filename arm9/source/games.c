/*
 * Game catalog for the emulator.
 */
#include <string.h>
#include <strings.h>

#include "games.h"

#define GAME_POINTER(name) &game_##name,
const game_desc_t *const games[GAME_COUNT] = { GAME_CATALOG(GAME_POINTER) };
#undef GAME_POINTER

const int game_count = sizeof(games) / sizeof(games[0]);

/* File name of a path, ignoring the device ("sd:/roms/gnw/x.gnw") and folders. */
static const char *file_name(const char *path){
    const char *name = path;
    for (const char *p = path; *p; p++){
        if (*p == '/' || *p == '\\')
            name = p + 1;
    }
    return name;
}

/* Matches the .gnw by file name, so it can live in any folder ("/roms/gnw/"),
   be opened from any device or have a different extension case. */
const game_desc_t *games_find_by_file(const char *path){
    if (!path || !path[0]) return NULL;
    const char *name = file_name(path);
    for (int i = 0; i < game_count; i++){
        if (strcasecmp(name, file_name(games[i]->rom_path)) == 0)
            return games[i];
    }
    return NULL;
}

/* Identity of the .gnw according to its own header: the CPU alone is not enough
   (Popeye, Manhole, Mario... exist on more than one CPU) and neither is the
   signature, so both are compared. */
const game_desc_t *games_find_by_rom(const char *cpu_name, const char *rom_sig){
    if (!cpu_name || !cpu_name[0] || !rom_sig || !rom_sig[0]) return NULL;
    size_t len = strlen(rom_sig);
    if (len != 8) return NULL;                 /* 8 bytes in the header */

    for (int i = 0; i < game_count; i++){
        const game_desc_t *g = games[i];
        if (!g->cpu || !g->rom_sig) continue;
        /* Only 5 characters are significant in the CPU name of the header:
           SM5A_, SM500, SM510, SM511, SM512 (ROM_CPU_* in gw_romloader.h). */
        if (strncmp(cpu_name, g->cpu, 5) != 0) continue;
        if (strncmp(rom_sig, g->rom_sig, len) != 0) continue;
        return g;
    }
    return NULL;
}



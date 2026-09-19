/*
 * Port of the LCD Game Emulator (https://github.com/bzhxx/lcd_game_emulator)
 * Original author: bzhxx — GPLv3 license.
 *
 * Nintendo DS adaptation (GameNWatchDS): each game is a self-contained
 * .gnw file read from the SD card (/gnw/ folder). The .gnw contains the SM5xx
 * program, the LCD geometry, the keyboard table and the TWO RGB565 backdrops
 * (topNS + bottomNS) in the background_pixel object. It is loaded into a RAM
 * buffer and accessed through direct pointers (no intermediate copies).
 */
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <assert.h>

#include "gw_type_defs.h"
#include "gw_system.h"
#include "gw_romloader.h"

/* Load buffer: the largest .gnw (dkong2) takes ~226 KB with the backdrops. */
static unsigned char gw_rom_buffer[GW_ROM_MAX_SIZE];
static unsigned int loaded_rom_size = 0;

unsigned char *gw_segments = NULL;
unsigned short *gw_segments_x = NULL;
unsigned short *gw_segments_y = NULL;
unsigned short *gw_segments_width = NULL;
unsigned short *gw_segments_height = NULL;
unsigned int *gw_segments_offset = NULL;
unsigned char *gw_program = NULL;
unsigned char *gw_melody = NULL;
unsigned int *gw_keyboard = NULL;

gwromheader_t gw_head;

/* Validates one .gnw block: offset+size must fit inside the buffer
   (overflow protection against corrupt files) and offset must be aligned
   to the element size of the array (no unaligned 16/32-bit reads). */
static bool block_ok(const char *name, unsigned int offset, unsigned int size,
                     unsigned int rom_size, unsigned int align)
{
   if (size == 0)
   {
      printf("GW block empty: %s\n", name);
      return false;
   }
   if (offset > rom_size || size > rom_size - offset)
   {
      printf("GW block out of range: %s (off=%u size=%u rom=%u)\n",
             name, offset, size, rom_size);
      return false;
   }
   if ((offset & (align - 1)) || (size & (align - 1)))
   {
      printf("GW block misaligned: %s (off=%u size=%u align=%u)\n",
             name, offset, size, align);
      return false;
   }
   return true;
}

bool gw_romloader_load(const unsigned char *rom, unsigned int rom_size)
{
   /* Stale pointers from a previously loaded game must not survive: in
      particular gw_melody, which changes the audio filter and the SM511
      melody path for the next game. */
   loaded_rom_size = 0;
   gw_segments = NULL;
   gw_segments_x = NULL;
   gw_segments_y = NULL;
   gw_segments_width = NULL;
   gw_segments_height = NULL;
   gw_segments_offset = NULL;
   gw_program = NULL;
   gw_melody = NULL;
   gw_keyboard = NULL;

   if (!rom || rom_size < sizeof(gw_head))
   {
      printf("GW header truncated: size=%u, header=%u\n",
             rom_size, (unsigned int)sizeof(gw_head));
      return false;
   }

   /* Read the ROM header. */
   memcpy(&gw_head, rom, sizeof(gw_head));

   /* Validate EVERY block of the header: offset+size must stay inside the
      buffer (a corrupt .gnw must fail to load, not read out of bounds), and
      the 16/32-bit arrays must be aligned (no unaligned reads on ARM9). */
   if (!block_ok("segments_pixel", gw_head.segments_pixel, gw_head.segments_pixel_size, rom_size, 1) ||
       !block_ok("segments_offset", gw_head.segments_offset, gw_head.segments_offset_size, rom_size, 4) ||
       !block_ok("segments_x", gw_head.segments_x, gw_head.segments_x_size, rom_size, 2) ||
       !block_ok("segments_y", gw_head.segments_y, gw_head.segments_y_size, rom_size, 2) ||
       !block_ok("segments_width", gw_head.segments_width, gw_head.segments_width_size, rom_size, 2) ||
       !block_ok("segments_height", gw_head.segments_height, gw_head.segments_height_size, rom_size, 2) ||
       !block_ok("program", gw_head.program, gw_head.program_size, rom_size, 1) ||
       !block_ok("keyboard", gw_head.keyboard, gw_head.keyboard_size, rom_size, 4))
      return false;
   if (gw_head.melody_size != 0 &&
       !block_ok("melody", gw_head.melody, gw_head.melody_size, rom_size, 1))
      return false;
   if (gw_head.background_pixel_size != 0 &&
       !block_ok("background_pixel", gw_head.background_pixel, gw_head.background_pixel_size, rom_size, 1))
      return false;

   /* Preserve the format invariant that the final block ends exactly at EOF.
      This is evaluated only after block_ok(), so offset+size cannot overflow. */
   unsigned int rom_size_expected = gw_head.keyboard + gw_head.keyboard_size;
   if (gw_head.background_pixel_size != 0)
      rom_size_expected = gw_head.background_pixel + gw_head.background_pixel_size;
   if (rom_size != rom_size_expected)
   {
      printf("ROM ERROR, size=%u, expected=%u\n", rom_size, rom_size_expected);
      return false;
   }

   /* Direct pointers to the embedded objects (read-only). */
   gw_segments = (unsigned char *)&rom[gw_head.segments_pixel];
   gw_segments_x = (unsigned short *)&rom[gw_head.segments_x];
   gw_segments_y = (unsigned short *)&rom[gw_head.segments_y];
   gw_segments_width = (unsigned short *)&rom[gw_head.segments_width];
   gw_segments_height = (unsigned short *)&rom[gw_head.segments_height];
   gw_segments_offset = (unsigned int *)&rom[gw_head.segments_offset];
   gw_program = (unsigned char *)&rom[gw_head.program];

   if (gw_head.melody_size != 0)
      gw_melody = (unsigned char *)&rom[gw_head.melody];

   /* Direct pointer to the keyboard table (read-only, like the rest). */
   gw_keyboard = (unsigned int *)&rom[gw_head.keyboard];

   printf("ROM loaded: %u bytes\n", rom_size);
   loaded_rom_size = rom_size;
   return true;
}

/* Reads the .gnw from the SD card (/gnw/ folder) and processes it. */
bool gw_romloader_load_file(const char *path)
{
   FILE *f = fopen(path, "rb");
   if (!f)
   {
      printf("GW not found: %s\n", path);
      return false;
   }

   fseek(f, 0, SEEK_END);
   long sz = ftell(f);
   fseek(f, 0, SEEK_SET);

   if (sz <= 0 || (unsigned long)sz > GW_ROM_MAX_SIZE)
   {
      printf("GW bad size: %ld\n", sz);
      fclose(f);
      return false;
   }

   size_t n = fread(gw_rom_buffer, 1, (size_t)sz, f);
   fclose(f);
   if (n != (size_t)sz)
      return false;

   return gw_romloader_load(gw_rom_buffer, (unsigned int)n);
}

/* Returns the indexed backdrop of the loaded .gnw: 0 = topNS (SUB),
   1 = bottomNS (MAIN). Each backdrop is GW_BACKDROP_SIZE RGB565 bytes.
   NULL if there are none. */
const unsigned char *gw_rom_backdrop(int index)
{
   if (gw_head.background_pixel_size < GW_BACKDROP_SIZE * GW_BACKDROPS)
      return NULL;
   if (index < 0 || index >= GW_BACKDROPS)
      return NULL;
   return &gw_rom_buffer[gw_head.background_pixel + index * GW_BACKDROP_SIZE];
}

/* Loads (or reloads) the active ROM of the current game. */
bool gw_romloader()
{
   return gw_romloader_load(gw_rom_buffer, loaded_rom_size);
}
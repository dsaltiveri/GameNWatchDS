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

/* Load buffer: current packages peak around 235 KiB; keep some headroom. */
static unsigned char gw_rom_buffer[GW_ROM_MAX_SIZE];
static unsigned int loaded_rom_size = 0;
static const unsigned char *loaded_rom = NULL;
static gw_load_error_t load_error = GW_LOAD_OK;
gw_load_error_t gw_romloader_error(void) { return load_error; }

#define GW_SEGMENT_COUNT 256U
#define GW_KEYBOARD_MIN_ENTRIES 9U
#define GW_KEYBOARD_MAX_ENTRIES 10U
#define GW_PROGRAM_SIZE 4096U
#define GW_MELODY_SIZE 256U
#define GW_LCD_WIDTH 256U
#define GW_LCD_HEIGHT_MAX 384U

/* Some historical packages contain nine keyboard rows while the system layer
   exposes a tenth (B) row. Copy into a fixed, zero-filled table so both valid
   package variants are safe without changing the .gnw format. */
static unsigned int gw_keyboard_storage[GW_KEYBOARD_MAX_ENTRIES];

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

static void clear_loaded_rom(void)
{
   loaded_rom_size = 0;
   loaded_rom = NULL;
   gw_segments = NULL;
   gw_segments_x = NULL;
   gw_segments_y = NULL;
   gw_segments_width = NULL;
   gw_segments_height = NULL;
   gw_segments_offset = NULL;
   gw_program = NULL;
   gw_melody = NULL;
   gw_keyboard = NULL;
   memset(&gw_head, 0, sizeof(gw_head));
   memset(gw_keyboard_storage, 0, sizeof(gw_keyboard_storage));
}

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

typedef struct gw_block_s
{
   const char *name;
   unsigned int offset;
   unsigned int size;
} gw_block_t;

static bool blocks_do_not_overlap(const gw_block_t *blocks, unsigned int count)
{
   for (unsigned int i = 0; i < count; i++)
   {
      if (blocks[i].size == 0)
         continue;
      if (blocks[i].offset < sizeof(gw_head))
      {
         printf("GW block overlaps header: %s\n", blocks[i].name);
         return false;
      }
      for (unsigned int j = i + 1; j < count; j++)
      {
         if (blocks[j].size == 0)
            continue;
         unsigned int i_end = blocks[i].offset + blocks[i].size;
         unsigned int j_end = blocks[j].offset + blocks[j].size;
         if (blocks[i].offset < j_end && blocks[j].offset < i_end)
         {
            printf("GW blocks overlap: %s and %s\n",
                   blocks[i].name, blocks[j].name);
            return false;
         }
      }
   }
   return true;
}

static bool exact_format_sizes(void)
{
   if (strncmp(gw_head.cpu_name, ROM_CPU_SM500, 5) != 0 &&
       strncmp(gw_head.cpu_name, ROM_CPU_SM5A, 5) != 0 &&
       strncmp(gw_head.cpu_name, ROM_CPU_SM510, 5) != 0 &&
       strncmp(gw_head.cpu_name, ROM_CPU_SM511, 5) != 0 &&
       strncmp(gw_head.cpu_name, ROM_CPU_SM512, 5) != 0)
   {
      printf("GW unsupported CPU: %.8s\n", gw_head.cpu_name);
      return false;
   }
   if (gw_head.segments_offset_size != GW_SEGMENT_COUNT * sizeof(unsigned int) ||
       gw_head.segments_x_size != GW_SEGMENT_COUNT * sizeof(unsigned short) ||
       gw_head.segments_y_size != GW_SEGMENT_COUNT * sizeof(unsigned short) ||
       gw_head.segments_width_size != GW_SEGMENT_COUNT * sizeof(unsigned short) ||
       gw_head.segments_height_size != GW_SEGMENT_COUNT * sizeof(unsigned short))
   {
      printf("GW invalid geometry array sizes\n");
      return false;
   }
   if (gw_head.program_size != GW_PROGRAM_SIZE)
   {
      printf("GW invalid program size: %u\n", gw_head.program_size);
      return false;
   }
   if (gw_head.keyboard_size != GW_KEYBOARD_MIN_ENTRIES * sizeof(unsigned int) &&
       gw_head.keyboard_size != GW_KEYBOARD_MAX_ENTRIES * sizeof(unsigned int))
   {
      printf("GW invalid keyboard size: %u\n", gw_head.keyboard_size);
      return false;
   }
   if (gw_head.melody_size != 0 && gw_head.melody_size != GW_MELODY_SIZE)
   {
      printf("GW invalid melody size: %u\n", gw_head.melody_size);
      return false;
   }
   if ((strncmp(gw_head.cpu_name, ROM_CPU_SM511, 5) == 0 ||
        strncmp(gw_head.cpu_name, ROM_CPU_SM512, 5) == 0) &&
       gw_head.melody_size != GW_MELODY_SIZE)
   {
      printf("GW melody required for %.8s\n", gw_head.cpu_name);
      return false;
   }
   if (gw_head.background_pixel_size != GW_BACKDROP_SIZE * GW_BACKDROPS)
   {
      printf("GW invalid backdrop size: %u\n", gw_head.background_pixel_size);
      return false;
   }
   return true;
}

static bool geometry_ok(const unsigned char *rom)
{
   const unsigned int *offsets =
      (const unsigned int *)&rom[gw_head.segments_offset];
   const unsigned short *xs =
      (const unsigned short *)&rom[gw_head.segments_x];
   const unsigned short *ys =
      (const unsigned short *)&rom[gw_head.segments_y];
   const unsigned short *widths =
      (const unsigned short *)&rom[gw_head.segments_width];
   const unsigned short *heights =
      (const unsigned short *)&rom[gw_head.segments_height];
   unsigned int pixel_nibbles = gw_head.segments_pixel_size * 2U;

   for (unsigned int segment = 0; segment < GW_SEGMENT_COUNT; segment++)
   {
      unsigned int width = widths[segment];
      unsigned int height = heights[segment];
      unsigned int offset = offsets[segment];

      if (width == 0 && height == 0)
      {
         if (offset != 0 || xs[segment] != 0 || ys[segment] != 0)
         {
            printf("GW invalid empty segment: %u\n", segment);
            return false;
         }
         continue;
      }
      if (width == 0 || height == 0 ||
          width > GW_LCD_WIDTH || height > GW_LCD_HEIGHT_MAX ||
          xs[segment] > GW_LCD_WIDTH - width ||
          ys[segment] > GW_LCD_HEIGHT_MAX - height)
      {
         printf("GW invalid segment geometry: %u\n", segment);
         return false;
      }

      unsigned int area = width * height;
      if (offset > pixel_nibbles || area > pixel_nibbles - offset)
      {
         printf("GW segment pixels out of range: %u\n", segment);
         return false;
      }
   }
   return true;
}

static bool parse_rom(const unsigned char *rom, unsigned int rom_size)
{
   if (!rom || rom_size < sizeof(gw_head))
   {
      printf("GW header truncated: size=%u, header=%u\n",
             rom_size, (unsigned int)sizeof(gw_head));
      return false;
   }

   /* Read the ROM header. */
   memcpy(&gw_head, rom, sizeof(gw_head));

   if (!exact_format_sizes())
      return false;

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
   if (!block_ok("background_pixel", gw_head.background_pixel,
                 gw_head.background_pixel_size, rom_size, 2))
      return false;

   const gw_block_t blocks[] = {
      {"segments_pixel", gw_head.segments_pixel, gw_head.segments_pixel_size},
      {"segments_offset", gw_head.segments_offset, gw_head.segments_offset_size},
      {"segments_x", gw_head.segments_x, gw_head.segments_x_size},
      {"segments_y", gw_head.segments_y, gw_head.segments_y_size},
      {"segments_width", gw_head.segments_width, gw_head.segments_width_size},
      {"segments_height", gw_head.segments_height, gw_head.segments_height_size},
      {"melody", gw_head.melody, gw_head.melody_size},
      {"program", gw_head.program, gw_head.program_size},
      {"keyboard", gw_head.keyboard, gw_head.keyboard_size},
      {"background_pixel", gw_head.background_pixel,
       gw_head.background_pixel_size},
   };
   if (!blocks_do_not_overlap(blocks, sizeof(blocks) / sizeof(blocks[0])) ||
       !geometry_ok(rom))
      return false;

   if (gw_head.melody_size != 0)
      for (unsigned int i = 0; i < GW_MELODY_SIZE; i++)
      {
         unsigned char note = rom[gw_head.melody + i];
         if ((note & 0xc0) || (note & 0x0f) > 13)
         {
            printf("GW invalid melody command at %u\n", i);
            return false;
         }
      }

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

   /* Normalize legacy nine-row tables to the ten safe rows consumed by the
      system layer. The source package and its on-disk format remain unchanged. */
   memcpy(gw_keyboard_storage, &rom[gw_head.keyboard], gw_head.keyboard_size);
   gw_keyboard = gw_keyboard_storage;

   printf("ROM loaded: %u bytes\n", rom_size);
   loaded_rom_size = rom_size;
   loaded_rom = rom;
   return true;
}

bool gw_romloader_load(const unsigned char *rom, unsigned int rom_size)
{
   clear_loaded_rom();
   load_error = GW_LOAD_INVALID;
   if (!parse_rom(rom, rom_size))
   {
      clear_loaded_rom();
      return false;
   }
   load_error = GW_LOAD_OK;
   return true;
}

/* Reads the .gnw from the SD card (/gnw/ folder) and processes it. */
bool gw_romloader_load_file(const char *path)
{
   clear_loaded_rom();
   load_error = GW_LOAD_READ_ERROR;
   FILE *f = fopen(path, "rb");
   if (!f)
   {
      load_error = GW_LOAD_OPEN_ERROR;
      printf("GW not found: %s\n", path);
      return false;
   }

   if (fseek(f, 0, SEEK_END) != 0)
   {
      printf("GW could not seek: %s\n", path);
      fclose(f);
      return false;
   }
   long sz = ftell(f);
   if (sz < 0 || fseek(f, 0, SEEK_SET) != 0)
   {
      printf("GW could not read position: %s\n", path);
      fclose(f);
      return false;
   }

   if (sz <= 0 || (unsigned long)sz > GW_ROM_MAX_SIZE)
   {
      load_error = GW_LOAD_INVALID;
      printf("GW bad size: %ld\n", sz);
      fclose(f);
      return false;
   }

   size_t n = fread(gw_rom_buffer, 1, (size_t)sz, f);
   fclose(f);
   if (n != (size_t)sz)
      return false;

   bool ok = gw_romloader_load(gw_rom_buffer, (unsigned int)n);
   load_error = ok ? GW_LOAD_OK : GW_LOAD_INVALID;
   return ok;
}

/* Returns the indexed backdrop of the loaded .gnw: 0 = topNS (SUB),
   1 = bottomNS (MAIN). Each backdrop is GW_BACKDROP_SIZE RGB565 bytes.
   NULL if there are none. */
const unsigned char *gw_rom_backdrop(int index)
{
   if (!loaded_rom || gw_head.background_pixel_size < GW_BACKDROP_SIZE * GW_BACKDROPS)
      return NULL;
   if (index < 0 || index >= GW_BACKDROPS)
      return NULL;
   return &loaded_rom[gw_head.background_pixel + index * GW_BACKDROP_SIZE];
}

/* Loads (or reloads) the active ROM of the current game. */
bool gw_romloader()
{
   return gw_romloader_load(loaded_rom, loaded_rom_size);
}


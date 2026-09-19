/*
 * PC harness: loads a .gnw and runs the real emulator (core + gw_system +
 * gw_graphic) frame by frame, with configurable input. Used to diagnose:
 *  - crash / illegal core opcode
 *  - input mapping (histogram of firmware K reads via gw_readk_count)
 *  - whether the game writes segments (gw_calc_segment_states)
 *  - which PC/state each button and sequence ends up in
 * Build (from tools/_harness):
 *   gcc -O2 -DHARNESS_DEBUG harness.c ../../arm9/source/cpus/sm500core.c ../../arm9/source/cpus/sm500op.c \
 *       ../../arm9/source/cpus/sm5acore.c ../../arm9/source/cpus/sm510base.c \
 *       ../../arm9/source/cpus/sm510core.c ../../arm9/source/cpus/sm510op.c \
 *       ../../arm9/source/cpus/sm511core.c ../../arm9/source/gw_sys/gw_system.c \
 *       ../../arm9/source/gw_sys/gw_graphic.c \
 *       -I../../arm9/source/cpus -I../../arm9/source/gw_sys -I../../arm9/source -o harness.exe
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

#include "gw_type_defs.h"
#include "gw_romloader.h"
#include "gw_system.h"
#include "gw_graphic.h"
#include "sm510.h"

/* stubs that are not in gw_system.c/gw_graphic.c */
unsigned int gw_buttons_state = 0;
unsigned int gw_get_buttons(void) { return gw_buttons_state; }
bool gw_romloader(void) { return false; }   /* the harness loads the .gnw by hand */
unsigned char *gw_program = NULL;
unsigned char *gw_melody = NULL;
unsigned char *gw_segments = NULL;
unsigned short *gw_segments_x = NULL;
unsigned short *gw_segments_y = NULL;
unsigned short *gw_segments_width = NULL;
unsigned short *gw_segments_height = NULL;
unsigned int *gw_segments_offset = NULL;
unsigned int *gw_keyboard = NULL;
gwromheader_t gw_head;

/* Number of segments ON according to gw_calc_segment_states (real). */
static int seg_on_count(void)
{
    unsigned char seg[256];
    gw_calc_segment_states(seg);
    int on = 0;
    for (int i = 0; i < 256; i++) on += seg[i];
    return on;
}

static void print_histograma(void)
{
    for (int s = 0; s < 256; s++)
        for (int k = 0; k < 16; k++)
            if (gw_readk_count[s][k])
                printf("    S=%02X K=%X x%ld\n", s, k, gw_readk_count[s][k]);
}

int main(int argc, char **argv)
{
    if (argc < 2) { fprintf(stderr, "usage: harness <file.gnw>\n"); return 1; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", argv[1]); return 1; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    unsigned char *gw = malloc(sz);
    fread(gw, 1, sz, f); fclose(f);

    memcpy(&gw_head, gw, sizeof(gw_head));
    gw_program = gw + gw_head.program;
    gw_melody = (gw_head.melody_size ? gw + gw_head.melody : NULL);
    gw_keyboard = (unsigned int *)(gw + gw_head.keyboard);

    printf("ROM %s (%ld bytes) cpu=%s\n", argv[1], sz, gw_head.cpu_name);

    /* Initializes the real emulator (picks core, multikey, deflicker...). */
    if (!gw_system_config()) { printf("gw_system_config failed\n"); return 1; }
    gw_system_start();
    gw_system_reset();
    gw_system_sound_init();

    setvbuf(stdout, NULL, _IONBF, 0);

    /* per-button mode: see which state the game ends up in for each button */
    const char *buttons[] = { "NONE", "UP", "DOWN", "LEFT", "RIGHT", "GAME", "TIME", "A", "B" };
    const unsigned int vals[] = { 0, 0x02, 0x08, 0x01, 0x04, 0x80, 0x40, 0x10, 0x20 };
    for (int b = 0; b < 9; b++) {
        memset(gw_readk_count, 0, sizeof(gw_readk_count));
        gw_buttons_state = vals[b];
        gw_system_reset(); gw_system_sound_init();
        for (int f = 0; f < 600; f++) gw_system_run(GW_SYSTEM_CYCLES);  /* 10 seg */
        printf("--- button %-5s (0x%02X): seg_ON=%d m_bp=%d m_bc=%d prev_pc=%04X pc=%04X\n",
               buttons[b], vals[b], seg_on_count(), m_bp, m_bc, m_prev_pc, m_pc);
        print_histograma();
    }

    /* frame-by-frame simulation with a configurable sequence (script in buttons[]) */
    printf("\n===== FRAME-BY-FRAME SIMULATION (script: GAME, A, GAME) =====\n");
    const unsigned int script[24] = {0,0,0,0x80,0x80,0x80,0x80,0,0,0x10,0x10,0x10,
                                    0,0,0x80,0x80,0x80,0,0,0,0,0,0,0};
    gw_buttons_state = 0;
    gw_system_reset(); gw_system_sound_init();
    memset(gw_readk_count, 0, sizeof(gw_readk_count));
    for (long f = 0; f < 300; f++) {
        if (f < 24) gw_buttons_state = script[f];   /* first 24 frames follow the script */
        gw_system_run(GW_SYSTEM_CYCLES);
        if (f % 10 == 0)
            printf("  frame=%3ld btn=%02X seg_ON=%d prev_pc=%04X pc=%04X\n",
                   f, gw_buttons_state, seg_on_count(), m_prev_pc, m_pc);
    }

    printf("\nDONE\n");
    free(gw);
    return 0;
}

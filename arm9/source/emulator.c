/*
 * Unified G&W emulator for Nintendo DS (GameNWatchDS).
 * Common emulator core: LCD rendered as merged 64x64 sprites, a 16bpp BG3
 * background and audio driven by a real 32-bit odometer of DAC cycles.
 * It unifies the code shared by all G&W games. What is specific to each game
 * (keys, tate mode, keyboard patches, ROM and backgrounds) lives in
 * games/game_*.c + the .s of games/<game>/, described by game_desc_t.
 */
#include <nds.h>
#include <stdio.h>
#include <string.h>

#include "gw_sys/gw_type_defs.h"
#include "gw_sys/gw_system.h"
#include "gw_sys/gw_graphic.h"
#include "gw_sys/gw_romloader.h"
#include "emulator.h"

#define TILE 64
#define TILES_X 4          /* 256 / 64 */
#define TILES_Y 3          /* 192 / 64 */
#define TILES_N (TILES_X * TILES_Y)  /* 12 sprites per screen */

static const game_desc_t *g_game = NULL;

/* RGB565 backgrounds of the current game, extracted from the .gnw loaded in RAM. */
static const unsigned char *g_top_bmp = NULL;     /* topNS  -> SUB screen */
static const unsigned char *g_bottom_bmp = NULL;  /* bottomNS -> MAIN screen */

/* Current G&W button state (published for gw_system.c). */
u32 gw_buttons_state = 0;

/* Input API used by gw_system.c (gw_readK/gw_readB/gw_readBA). */
unsigned int gw_get_buttons(void){ return gw_buttons_state; }

#define AUDIO_SAMPLES GW_AUDIO_BUFFER_LENGTH   /* 546 = 32768/60 */
#define AUDIO_LOOP_FRAMES 16                     /* 16-frame headroom in the loop buffer */
#define AUDIO_LOOP_LEN (AUDIO_SAMPLES * AUDIO_LOOP_FRAMES)

static s16 audio_pcm[AUDIO_SAMPLES] __attribute__((aligned(4)));
static s16 audio_loop[AUDIO_LOOP_LEN] __attribute__((aligned(4)));

#define SEG_SPRITE_COLOR RGB15(0,0,0)  /* segment color from the SVG: #000000 */

typedef struct {
    OamState *oam;
    u8  pixel_seg[FBH][FBW];      /* pixel -> segment (0xFF = empty) */
    u8  pixel_int[FBH][FBW];      /* 4-bit intensity of the pixel (0-15) */
    u8  pixel_seg2[FBH][FBW];     /* 2nd segment claiming the pixel (0xFF = empty) */
    u8  pixel_int2[FBH][FBW];     /* its 4-bit intensity (OR, like the reference emulator) */
    u8 *tile_gfx[TILES_N];        /* VRAM of the 12 64x64 tiles */
    u8  tile_dirty[TILES_N];
    u8  seg_tiles[256][TILES_N];  /* segment -> tiles it touches (0xFF = end) */
    u8  seg_tiles_tate[256][TILES_N]; /* same, tate orientation (rotated) */
    unsigned char seg_prev[256];
    int  esc_y0;                  /* first pixel_seg row of the scene */
    void *tate_src;               /* scene this screen shows in tate */
    const u16 *bg;                /* RGB565 background from the .gnw (color artwork) */
    u16 *fb;                      /* BG3 framebuffer (BG_GFX / BG_GFX_SUB) */
} screen_t;

/* Multiples the background RGB by the segment intensity (0-255), same as
   rgb_multiply_8bits in LCD-Game-Emulator. The background is NDS Bmp16
   (0x8000 | B5<<10 | G5<<5 | R5); bit 15 (opaque) is preserved. */
static inline u16 rgb_multiply_nds(u16 bg, u8 sg){
    u32 r = (bg & 0x1F) * sg >> 8;
    u32 g = ((bg >> 5) & 0x1F) * sg >> 8;
    u32 b = ((bg >> 10) & 0x1F) * sg >> 8;
    return (u16)(0x8000 | (b << 10) | (g << 5) | r);
}

static screen_t scr_main;
static screen_t scr_sub;

/* ---------------- audio ---------------- */
/* Converts the buzzer value (bits 0/1) into PCM amplitude.
   Index 0..3: bit0 = +8000, bit1 = -8000 (differential). */
static const s16 audio_levels[4] = { 0, 8000, -8000, 0 };

/* 100% reliable audio synchronisation.
   It measures the REAL elapsed cycles with a 32-bit odometer (TIMER0+TIMER1
   in cascade, no IRQ) and writes exactly the samples the DAC consumes,
   accumulating the remainder in 16.16 fixed point (never lost). With the
   exact AUDIO_CPS (below) the fractional remainder is bounded and the net
   drift is mathematically zero. The emulator advances ONLY when the audio
   demands it (logical frames of 546 samples). */
static u32 audio_odometer = 0;
static u64 audio_frac = 0;              /* 16.16 accumulator of samples to write */
static int  audio_frame_pos = 0;        /* position within the logical 546-sample frame */
static int  audio_loop_idx = 2 * AUDIO_SAMPLES;  /* 2 frames ahead of the playback head */

/* libnds sound channel playing audio_loop in a loop. soundPlaySample()
   selects a free channel (round-robin); it must be killed when leaving the
   game (soundKill), because soundDisable() only silences the global output
   and leaves the channel looping: unless released, every game entry leaks a
   channel and after a few games the 16 channels run out and audio distorts. */
static int audio_channel = -1;

/* Exact, deterministic bus cycles per DAC sample.
   libnds sets the channel TMR for 32768 Hz to -511, and the hardware plays at
   BUS_CLOCK / ((0x10000 - TMR) * 2) = 1022 bus cycles per sample. It is the same
   formula on real hardware and in emulators (no$gba, melonDS...), so there is no
   uncertainty to measure: the DAC ALWAYS consumes 1022 cycles per sample with the
   TMR that libnds writes. */
#define AUDIO_CPS 1022

static u32 read_odometer(void)
{
    u16 lo, hi1, hi2;
    do {
        hi1 = TIMER1_DATA;
        lo  = TIMER0_DATA;
        hi2 = TIMER1_DATA;
    } while (hi1 != hi2);
    return ((u32)hi2 << 16) | lo;
}

/* --- Audio timbre improvement (post-processing of the buzzer level) ---
   The main loop paints the "raw" square wave (0/+8000, or 0/-8000 depending on
   the piezo flag). To get closer to the real G&W/MAME, a chain of 2 real-time
   filters is applied, one pass per sample of the already generated frame:

   1) 2nd-order Butterworth low-pass, fc ~8kHz at fs 32768Hz. The closed loop
      softens the square wave flanks and removes the metallic aliasing timbre
      (like the windowed-sinc filter in MAME's spkrdev.cpp).
   2) 1st-order DC-blocker (y = x - x_prev + a*y_prev). A real piezo is AC-coupled
      through a capacitor: it does not reproduce DC. Here we remove the DC
      offset of the SM511 melody and the edge pop of each note, making the output
      oscillate around 0 (bipolar, ~+-4000).

   Persistent state per channel, reset in gw_system_sound_init(). */
static int audio_bq_x1, audio_bq_x2, audio_bq_y1, audio_bq_y2;
static int audio_dcb_x1, audio_dcb_y1;

static void audio_reset_filters(void)
{
    audio_bq_x1 = audio_bq_x2 = audio_bq_y1 = audio_bq_y2 = 0;
    audio_dcb_x1 = audio_dcb_y1 = 0;
}

/* Synthesizes the frame into audio_pcm through the filter chain. */
static void audio_synth_frame(void)
{
    /* Biquad low-pass Butterworth coefficients, fs=32768Hz, Q=0.707.
       Direct Form 1 (y = b0·x + b1·x1 + b2·x2 - a1·y1 - a2·y2) with Q16
       factors. Computed via the RBJ formula and normalized by a0. Two
       cutoff frequencies depending on sound type (DC gain = 1.0 both):
       - With melody (SM511/512): fc=8kHz (b0=b2=0x483E, b1=0x907B,
         a1=-2827, a2=11265).
       - Without melody (SM510/SM5A, divider beeps): fc=6kHz
         (b0=b2=0x2E0C, b1=0x5C17, a1=-32501, a2=14116). */
    int b0, b1, b2, a1, a2;
    if (gw_melody) {
        /* SM511/512 (melody): 8kHz cutoff, keeps the full tone */
        b0 = 0x483E; b1 = 0x907B; b2 = 0x483E;
        a1 = -2827;  a2 = 11265;
    } else {
        /* SM510/SM5A (divider beeps): 6kHz cutoff, tighter (less metallic) */
        b0 = 0x2E0C; b1 = 0x5C17; b2 = 0x2E0C;
        a1 = -32501; a2 = 14116;
    }

    for(int i=0;i<AUDIO_SAMPLES;i++){
        int x = audio_levels[gw_audio_buffer[i] & 3];

        /* --- biquad low-pass ---
           Products and sum stay within int32: |x|,|y|<=8000 -> max ~700M < 2^31.
           s64 (muldi3) is avoided for speed on the ARM9. */
        int y = x * b0 + audio_bq_x1 * b1 + audio_bq_x2 * b2
              - audio_bq_y1 * a1 - audio_bq_y2 * a2;
        y >>= 16;                        /* normalize the Q16 gain */
        audio_bq_x2 = audio_bq_x1; audio_bq_x1 = x;
        audio_bq_y2 = audio_bq_y1; audio_bq_y1 = y;

        /* --- DC-blocker --- */
        int z = y - audio_dcb_x1 + (((audio_dcb_y1) * 14387) >> 14); /* 0.878 */
        audio_dcb_x1 = y;
        audio_dcb_y1 = z;

        /* --- clip-safe --- */
        if(z >  32767) z =  32767;
        if(z < -32767) z = -32767;
        audio_pcm[i] = (s16)z;
    }
}

/* Writes exactly n samples into the ring buffer, running the emulator's
   logical frames (546 samples) whenever the current frame is exhausted. */
static void audio_write_samples(int n)
{
    int pos = audio_frame_pos;
    int left = AUDIO_SAMPLES - pos;
    while(n > 0){
        if(left == 0){
            gw_system_run(GW_SYSTEM_CYCLES);
            audio_synth_frame();
            pos = 0;
            left = AUDIO_SAMPLES;
        }
        int c = (n < left) ? n : left;
        for(int i=0;i<c;i++)
            audio_loop[(audio_loop_idx + i) % AUDIO_LOOP_LEN] = audio_pcm[pos + i];
        audio_loop_idx = (audio_loop_idx + c) % AUDIO_LOOP_LEN;
        pos += c; n -= c; left -= c;
    }
    audio_frame_pos = pos;
    DC_FlushRange(audio_loop, sizeof(audio_loop));
}

/* ---------------- LCD render by tiles ---------------- */
static void init_screen(screen_t *s, OamState *oam){
    memset(s, 0, sizeof(*s));
    s->oam = oam;

    memset(s->pixel_seg, 0xFF, sizeof(s->pixel_seg));
    memset(s->pixel_int, 0, sizeof(s->pixel_int));
    memset(s->pixel_seg2, 0xFF, sizeof(s->pixel_seg2));
    memset(s->pixel_int2, 0, sizeof(s->pixel_int2));
    memset(s->seg_tiles, 0xFF, sizeof(s->seg_tiles));
    memset(s->seg_tiles_tate, 0xFF, sizeof(s->seg_tiles_tate));

    /* Render (normal and inverted) writes directly to BG3 via
       rebuild_tile; no sprites are used. */
    return;
}

/* Rebuilds a tile of screen s's framebuffer.
   In tate mode it samples the scene (s->tate_src) through the inverse
   transform (CCW rotation + 3/4 scale); outside the scene it stays transparent. */
static void rebuild_tile(screen_t *s, int t, const unsigned char *seg_on){
    int ox = (t % TILES_X) * TILE;
    int oy = (t / TILES_X) * TILE;

    /* Inverted LCD (Panorama/Tabletop): the framebuffer is already black
       (background) and lit segment pixels show the artwork multiplied by the
       segment intensity (like rgb_multiply_8bits in LCD-Game-Emulator). It is
       written DIRECTLY to BG3 (no sprites). */
    if(g_game->lcd_inverted){
        const u16 *bg = s->bg;
        u16 *fb = s->fb;
        for(int yy=0; yy<TILE; yy++){
            int fy = oy + yy;
            if(fy < 0 || fy >= FBH) continue;
            for(int xx=0; xx<TILE; xx++){
                int fx = ox + xx;
                if(fx < 0 || fx >= FBW) continue;
                u16 c = 0;
                u8 sg = s->pixel_seg[fy][fx];
                u8 sg2 = s->pixel_seg2[fy][fx];
                if(sg != 0xFF && seg_on[sg]){
                    /* expand the 4-bit intensity to 8 bits (0x0F -> 0xFF) */
                    u8 n = s->pixel_int[fy][fx];
                    u8 cur8 = (u8)((n << 4) | n);
                    c = rgb_multiply_nds(bg[fy*FBW + fx], cur8);
                } else if(sg2 != 0xFF && seg_on[sg2]){
                    u8 n = s->pixel_int2[fy][fx];
                    u8 cur8 = (u8)((n << 4) | n);
                    c = rgb_multiply_nds(bg[fy*FBW + fx], cur8);
                }
                fb[fy*FBW + fx] = c;
            }
        }
        return;
    }

    /* landscape (normal) mode: darken the background (artwork) by the segment
       intensity, like rgb_multiply_8bits in LCD-Game-Emulator (pure black ->
       39). Written directly to BG3. */
    const u16 *bg = s->bg;
    u16 *fb = s->fb;
    for(int yy=0; yy<TILE; yy++){
        int fy = oy + yy;
        if(fy < 0 || fy >= FBH) continue;
        for(int xx=0; xx<TILE; xx++){
            int fx = ox + xx;
            if(fx < 0 || fx >= FBW) continue;
            u16 c = bg[fy*FBW + fx];
            u8 sg = s->pixel_seg[fy][fx];
            u8 sg2 = s->pixel_seg2[fy][fx];
            u8 cur8 = 255;
            if(sg != 0xFF && seg_on[sg]){
                u8 n = s->pixel_int[fy][fx];
                cur8 = (u8)((n << 4) | n);
                if(cur8 == 0) cur8 = 39;
            } else if(sg2 != 0xFF && seg_on[sg2]){
                u8 n = s->pixel_int2[fy][fx];
                cur8 = (u8)((n << 4) | n);
                if(cur8 == 0) cur8 = 39;
            }

            /* cur8=255 (no segment): do not multiply; rgb_multiply_nds(c,255) is not the identity and would darken the background. */
            u16 base = (cur8 == 255) ? c : rgb_multiply_nds(c, cur8);
            /* Option B: colored floor per band (overlay tint). A lit segment does not
               fall to pure black but to its band's (column) color. */
            if(g_game->seg_floor && g_game->seg_floor_bands && fy >= g_game->seg_floor_y0){
                int band, apply = 1;
                if(g_game->seg_floor_h){
                    /* horizontal bands: by row (fy) */
                    if(g_game->seg_floor_limits){
                        /* non-uniform bands: Y bounds on the canvas (subtract
                           seg_floor_y0); outside the stripe range it is not
                           tinted (the Frame2 white line does not paint) */
                        int ly = fy - g_game->seg_floor_y0;
                        if(ly < g_game->seg_floor_limits[0] ||
                           ly >= g_game->seg_floor_limits[g_game->seg_floor_bands])
                            apply = 0;
                        else {
                            band = 0;
                            while(band < g_game->seg_floor_bands - 1 &&
                                   ly >= g_game->seg_floor_limits[band + 1])
                                band++;
                        }
                    } else if(g_game->seg_floor_band_w > 0)
                        band = (fy - g_game->seg_floor_y0) / g_game->seg_floor_band_w;
                    else
                        band = (fy * g_game->seg_floor_bands) / FBH;
                } else {
                    if(g_game->seg_floor_limits){
                        /* non-uniform vertical bands: X bounds on the
                           framebuffer (fx); outside the range it is not tinted */
                        if(fx < g_game->seg_floor_limits[0] ||
                           fx >= g_game->seg_floor_limits[g_game->seg_floor_bands])
                            apply = 0;
                        else {
                            band = 0;
                            while(band < g_game->seg_floor_bands - 1 &&
                                   fx >= g_game->seg_floor_limits[band + 1])
                                band++;
                        }
                    } else if(g_game->seg_floor_band_w > 0)
                        band = (fx - g_game->seg_floor_x0) / g_game->seg_floor_band_w;
                    else
                        band = (fx * g_game->seg_floor_bands) / FBW;
                }
                if(apply){
                if(band < 0) band = 0;
                if(band >= g_game->seg_floor_bands) band = g_game->seg_floor_bands - 1;
                u16 floor = g_game->seg_floor[band];
                u32 fr = (floor & 0x1F) * 8, fg = ((floor >> 5) & 0x1F) * 8;
                u32 fbb = ((floor >> 10) & 0x1F) * 8;
                u32 br = (base & 0x1F) * 8, bgc = ((base >> 5) & 0x1F) * 8;
                u32 bb = ((base >> 10) & 0x1F) * 8;
                u32 w = cur8, inv = 255 - cur8;
                u32 orr = (br * w + fr * inv) / 255;
                u32 og = (bgc * w + fg * inv) / 255;
                u32 ob = (bb * w + fbb * inv) / 255;
                c = (u16)(0x8000 | ((ob >> 3) << 10) | ((og >> 3) << 5) | (orr >> 3));
                } else {
                    c = base;
                }
            } else {
                c = base;
            }
            fb[fy*FBW + fx] = c;
        }
    }
}

/* Updates the sprites of disp with the segments of scene.
   In landscape and tate, scene == disp: each screen shows its own scene. */
static void update_screen(screen_t *scene, screen_t *disp,
                          const unsigned char *seg_on){
    /* Segment->tiles table depending on the mode: in tate the scene is rotated
       (seg_tiles_tate), in landscape the normal table (seg_tiles). */
    const u8 (*tlist)[TILES_N] = scene->seg_tiles;
    /* mark tiles touched by segments that changed */
    for(int seg=0; seg<256; seg++){
        if(seg_on[seg] != scene->seg_prev[seg]){
            for(int i=0; i<TILES_N; i++){
                u8 t = tlist[seg][i];
                if(t == 0xFF) break;
                if(t < TILES_N) disp->tile_dirty[t] = 1;
            }
            scene->seg_prev[seg] = seg_on[seg];
        }
    }

    /* rebuild dirty tiles */
    for(int t=0; t<TILES_N; t++){
        if(disp->tile_dirty[t]){
            rebuild_tile(disp, t, seg_on);
            disp->tile_dirty[t] = 0;
        }
    }
}

/* ---------------- rotated (tate) mode: tables and backdrops ---------------- */
/* Copies the landscape backgrounds to the framebuffer depending on the
   game config (bg assignment).
   In inverted LCD mode (Panorama/Tabletop) the background stays black:
   colored artwork is revealed ONLY where segment sprites display pixels. */
static void dma_backdrops(void){
    if(g_game->lcd_inverted){
        dmaFillWords(0x0000, BG_GFX, FBW*FBH*2);
        dmaFillWords(0x0000, BG_GFX_SUB, FBW*FBH*2);
    } else if(g_game->main_uses_top){
        dmaCopy(g_top_bmp, BG_GFX, FBW*FBH*2);
        dmaCopy(g_bottom_bmp, BG_GFX_SUB, FBW*FBH*2);
    } else {
        dmaCopy(g_bottom_bmp, BG_GFX, FBW*FBH*2);
        dmaCopy(g_top_bmp, BG_GFX_SUB, FBW*FBH*2);
    }
}

/* ---------------- init and main loop ---------------- */
/* build_maps() is defined below (next to the render), but emulator_init()
   needs it; a forward declaration lets it be used without warnings. */
static void build_maps(void);

/* Returns 1 on successful init, 0 on failure (ROM not found). */
static int emulator_init(void){
    powerOn(POWER_ALL_2D);

    videoSetMode(MODE_5_2D);
    videoSetModeSub(MODE_5_2D);

    vramSetBankA(VRAM_A_MAIN_BG);
    vramSetBankB(VRAM_B_MAIN_SPRITE);
    vramSetBankC(VRAM_C_SUB_BG);
    vramSetBankD(VRAM_D_SUB_SPRITE);

    bgInit(3, BgType_Bmp16, BgSize_B16_256x256, 0, 0);
    bgInitSub(3, BgType_Bmp16, BgSize_B16_256x256, 0, 0);
    videoBgEnable(3);
    videoBgEnableSub(3);

    /* Loads the .gnw from the SD card: it contains the program, segments,
       keyboard and the TWO RGB565 backgrounds (topNS + bottomNS). */
    if(!gw_romloader_load_file(g_game->rom_path))
        return 0;
    g_top_bmp = gw_rom_backdrop(0);
    g_bottom_bmp = gw_rom_backdrop(1);
    if(!g_top_bmp || !g_bottom_bmp)
        return 0;

    dma_backdrops();

    oamInit(&oamMain, SpriteMapping_1D_64, false);
    oamInit(&oamSub, SpriteMapping_1D_64, false);
    oamEnable(&oamMain);
    oamEnable(&oamSub);

    SPRITE_PALETTE[1] = SEG_SPRITE_COLOR;
    SPRITE_PALETTE_SUB[1] = SEG_SPRITE_COLOR;

    init_screen(&scr_main, &oamMain);
    if(g_game->dual_screen)
        init_screen(&scr_sub, &oamSub);

    /* In inverted LCD the segments write directly to the BG3 framebuffer and
       read the color artwork from the .gnw background (topNS/bottomNS depending
       on the screen). Assigned AFTER init_screen() because the latter memset()s
       the struct. */
    scr_main.bg = (const u16*)(g_game->main_uses_top ? g_top_bmp : g_bottom_bmp);
    scr_sub.bg  = (const u16*)(g_game->main_uses_top ? g_bottom_bmp : g_top_bmp);
    scr_main.fb = BG_GFX;
    scr_sub.fb  = BG_GFX_SUB;

    gw_system_config(); gw_system_start(); gw_system_reset();

    soundEnable();
    gw_system_sound_init();
    audio_reset_filters();   /* zero the timbre filters for the new game */

    /* Clean start: empty the ring buffer and synthesis state so every game
       starts silent (the buffer still holds the previous game's audio until
       the loop overwrites it). */
    memset(audio_loop, 0, sizeof(audio_loop));
    audio_frame_pos = 0;
    audio_frac = 0;
    audio_loop_idx = 2 * AUDIO_SAMPLES;

    /* Starts continuous playback ONCE with loop=true
       over the whole circular buffer. */
    audio_channel = soundPlaySample(audio_loop, SoundFormat_16Bit, AUDIO_LOOP_LEN*sizeof(s16),
                    GW_AUDIO_FREQ, 127, 90, true, 0);

    /* Odometer of the actual DAC consumption: TIMER0 (prescaler 1) + TIMER1 in
       cascade. No interrupts: they are just 32-bit counters. */
    TIMER0_CR = 0;
    TIMER1_CR = 0;
    TIMER0_DATA = 0;
    TIMER1_DATA = 0;
    TIMER0_CR = TIMER_ENABLE | TIMER_DIV_1;
    TIMER1_CR = TIMER_ENABLE | TIMER_CASCADE;
    audio_odometer = read_odometer();

    if(g_game->init_screens) g_game->init_screens();
    build_maps();
    return 1;
}



int emulator_run(const game_desc_t *g){
    g_game = g;
    if(!emulator_init())
        return 0;   /* ROM not found or invalid: return to menu */

    unsigned char seg_on[256];
    memset(seg_on, 0, sizeof(seg_on));

    for(;;){
        scanKeys();
        u32 down = keysDown();
        u32 held = keysHeld();

        /* R: return to the main menu (L+R = ALARM, does not exit). */
        if((down & KEY_R) && !(held & KEY_L))
            break;

        gw_buttons_state = g_game->update_buttons();

        /* Measures the REAL DAC consumption since the last frame and writes
           exactly the consumed samples, accumulating the remainder in 16.16
           fixed point with the exact AUDIO_CPS: mathematically impossible drift. */
        u32 now = read_odometer();
        u32 delta = (u32)(now - audio_odometer);
        audio_odometer = now;

        audio_frac += ((u64)delta << 16) / AUDIO_CPS;
        int n = (int)(audio_frac >> 16);
        audio_frac &= 0xFFFF;

        /* Advances the emulator ONLY when the audio demands it and writes the n
           samples into the ring buffer, always ahead of the playback head. */
        audio_write_samples(n);

        /* Segment states: SM510/511 via RAM H, or SM5A via O/W outputs. */
        if(g_game->use_sm5a)
            gw_calc_segment_states_sm5a(seg_on);
        else
            gw_calc_segment_states(seg_on);

        update_screen(&scr_main, &scr_main, seg_on);
        if(g_game->dual_screen)
            update_screen(&scr_sub, &scr_sub, seg_on);

        swiWaitForVBlank();
        oamUpdate(&oamMain);
        oamUpdate(&oamSub);
    }

    /* Back to the menu: kill the audio channel (soundDisable() does not release
       the channel; without soundKill() every game leaves one active on loop
       and the DS runs out of its 16 channels) and stop the odometer. */
    if (audio_channel >= 0) soundKill(audio_channel);
    audio_channel = -1;
    soundDisable();
    TIMER0_CR = 0;
    TIMER1_CR = 0;
    return 1;
}



/* Precompute: pixel->segment and segment->tiles maps.
   In dual-screen games segments with gy0+h <= FBH go to the MAIN screen, the
   rest to SUB (the 192 separator). In single-screen games all go to MAIN with
   ly0 = gy0. */
static void build_maps(void){
    for(int seg=0; seg<256; seg++){
        int w = gw_segments_width[seg];
        int h = gw_segments_height[seg];
        if(w <= 0 || h <= 0) continue;

        int gx0 = gw_segments_x[seg];
        int gy0 = gw_segments_y[seg];
        unsigned int off = gw_segments_offset[seg];

        screen_t *s;
        int lx0, ly0;
        if(g_game->dual_screen){
            if(gy0 + h <= FBH){
                s = &scr_main; lx0 = gx0; ly0 = gy0;
            } else {
                s = &scr_sub;  lx0 = gx0; ly0 = gy0 - FBH;
            }
        } else {
            s = &scr_main; lx0 = gx0; ly0 = gy0;
        }

        /* pixel -> segment. Transparency depends on the mode:
           - inverted (Panorama/Tabletop): black background -> nibble 0
           - normal: white background -> nibble 0xF
           The non-transparent value is the segment intensity (0-15). */
        u8 transparent = g_game->lcd_inverted ? 0x0 : 0xF;
        for(int py=0; py<h; py++){
            int gy = ly0 + py;
            if(gy < 0 || gy >= FBH) continue;
            for(int px=0; px<w; px++){
                int gx = lx0 + px;
                if(gx < 0 || gx >= FBW) continue;
                unsigned int nib = off + (unsigned int)py*w + px;
                unsigned char b = gw_segments[nib >> 1];
                unsigned char n = (nib & 1) ? (b & 0xF) : (b >> 4);
                if(n != transparent){
                    if(s->pixel_seg[gy][gx] == 0xFF){
                        s->pixel_seg[gy][gx] = (u8)seg;
                        s->pixel_int[gy][gx] = n;
                    } else if(s->pixel_seg[gy][gx] != seg &&
                              s->pixel_seg2[gy][gx] == 0xFF){
                        /* 2nd segment claiming the same pixel: it is drawn if EITHER of the two
                           is lit (same as the OR in the LCD-Game-Emulator render). */
                        s->pixel_seg2[gy][gx] = (u8)seg;
                        s->pixel_int2[gy][gx] = n;
                    }
                }
            }
        }

        /* segment -> tiles it touches */
        int x0 = lx0, y0 = ly0;
        int x1 = lx0 + w - 1, y1 = ly0 + h - 1;
        if(x1 < 0 || y1 < 0 || x0 >= FBW || y0 >= FBH) continue;
        if(x0 < 0) x0 = 0;
        if(y0 < 0) y0 = 0;
        if(x1 >= FBW) x1 = FBW-1;
        if(y1 >= FBH) y1 = FBH-1;

        int n = 0;
        for(int ty=y0/TILE; ty<=y1/TILE; ty++){
            for(int tx=x0/TILE; tx<=x1/TILE; tx++){
                int t = ty*TILES_X + tx;
                if(t >= 0 && t < TILES_N)
                    s->seg_tiles[seg][n++] = (u8)t;
            }
        }
    }

}


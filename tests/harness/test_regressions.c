/* Test the real renderer, startup, ring writer and SM511 sample generation.
   Only the Nintendo DS hardware functions are replaced by host stand-ins. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../../arm9/source/emulator.c"
/* Include the core to compare against its actual per-clock melody callback. */
#include "../../arm9/source/cpus/sm511core.c"

static u32 no_buttons(void) { return 0; }
static int maps_ready;
static void prepare_maps(void) { maps_ready = 1; }

static void test_segment_255(void)
{
    static screen_t screen;
    unsigned char on[256] = {0};
    init_screen(&screen);
    assert(screen.pixel_seg[0][0] != 255);
    screen.pixel_seg[0][0] = 255;
    screen.pixel_int[0][0] = 3;
    on[255] = 1;
    assert(pixel_active_intensity(&screen, 0, 0, on, false) == 3);
    screen.pixel_seg2[0][0] = 254;
    screen.pixel_int2[0][0] = 7;
    on[254] = 1;
    assert(pixel_active_intensity(&screen, 0, 0, on, false) == 3);
    assert(pixel_active_intensity(&screen, 0, 0, on, true) == 7);
    on[255] = on[254] = 0;
    assert(pixel_active_intensity(&screen, 0, 0, on, false) == -1);
}

static void test_segment_maps(void)
{
    static unsigned short xs[256], ys[256], widths[256], heights[256];
    static unsigned int offsets[256];
    static unsigned char pixels[] = {0x37};
    static const game_desc_t game = { .dual_screen = 1 };
    gw_segments_x = xs; gw_segments_y = ys;
    gw_segments_width = widths; gw_segments_height = heights;
    gw_segments_offset = offsets; gw_segments = pixels;
    widths[254] = widths[255] = heights[254] = heights[255] = 1;
    offsets[254] = 1;
    g_game = &game;
    unsigned char on[256] = {0};
    on[255] = 1;
    for (int screen = 0; screen < 2; screen++) {
        ys[254] = ys[255] = screen * FBH;
        init_screen(&scr_main); init_screen(&scr_sub);
        build_maps();
        screen_t *map = screen ? &scr_sub : &scr_main;
        assert(map->pixel_seg2[0][0] == 255);
        assert(pixel_active_intensity(map, 0, 0, on, false) == 3);
        assert(map->seg_tiles[255][0] == 0);
    }
}

static void test_startup(const char *path)
{
    static const game_desc_t game = {
        .name = "Synthetic", .update_buttons = no_buttons,
        .init_screens = prepare_maps,
    };
    g_game = &game;
    g_rom_path = path;
    for (int pass = 0; pass < 2; pass++) {
        for (unsigned int i = 0; i < AUDIO_SAMPLES; i++) audio_pcm[i] = 1234;
        memset(audio_loop, 0x42, sizeof(audio_loop));
        host_flushed = host_played = maps_ready = 0;
        assert(emulator_init());
        assert(host_played && maps_ready);
        assert(audio_frame_pos == AUDIO_SAMPLES);
        for (unsigned int i = 0; i < AUDIO_SAMPLES; i++) assert(audio_pcm[i] == 0);
        for (unsigned int i = 0; i < AUDIO_LOOP_LEN; i++) assert(audio_loop[i] == 0);
        audio_write_samples(AUDIO_SAMPLES + 7);
        for (unsigned int i = 0; i < AUDIO_LOOP_LEN; i++) assert(audio_loop[i] == 0);
        soundKill(audio_channel);
    }
}

static void test_melody_continuity(bool halted, int divider)
{
    static unsigned int keyboard[10];
    static unsigned char program[4096];
    static unsigned char melody[256];
    enum { SAMPLES = GW_AUDIO_BUFFER_LENGTH * 40 };
    static unsigned char blocked[SAMPLES], continuous[SAMPLES];
    memset(melody, 2, sizeof(melody));
    memset(program, 0x5f, sizeof(program));
    gw_program = program;
    gw_keyboard = keyboard;
    gw_melody = melody;
    memcpy(gw_head.cpu_name, "SM511___", 8);
    gw_head.flags = 0;
    assert(gw_system_config());
    gw_system_start(); gw_system_reset(); gw_system_sound_init();
    m_halt = halted; m_clk_div = divider; m_melody_rd = 1;
    for (int i = 0; i < 40; i++) {
        gw_system_run(GW_SYSTEM_CYCLES);
        memcpy(blocked + i * GW_AUDIO_BUFFER_LENGTH, gw_audio_buffer,
               GW_AUDIO_BUFFER_LENGTH);
    }
    gw_system_start(); gw_system_reset(); gw_system_sound_init();
    m_halt = halted; m_clk_div = divider; m_melody_rd = 1;
    for (int i = 0; i < SAMPLES; i++) {
        /* Reference bypasses the block consumer; drain only the host sink. */
        gw_system_sound_init();
        sm511_div_timer_cb();
        continuous[i] = m_r_out;
    }
    assert(memcmp(blocked, continuous, SAMPLES) == 0);
    /* Short requests must also preserve tails across calls. */
    gw_system_start(); gw_system_reset(); gw_system_sound_init();
    m_halt = halted; m_clk_div = divider; m_melody_rd = 1;
    for (int i = 0; i < SAMPLES; i++) {
        gw_system_run(1);
        assert(gw_audio_buffer[0] == continuous[i]);
    }
    assert(gw_system_run(0) == 0);
    assert(gw_system_run(GW_AUDIO_BUFFER_LENGTH + 1) == 0);
}

static void test_invalid_melody_startup(const char *path)
{
    static const game_desc_t game = { .name = "Missing melody" };
    g_game = &game;
    g_rom_path = path;
    host_played = 0;
    assert(!emulator_init());
    assert(gw_romloader_error() == GW_LOAD_INVALID);
    assert(!host_played && !gw_program && !gw_melody);
    assert(!gw_rom_backdrop(0));
}

int main(int argc, char **argv)
{
    assert(argc == 3);
    test_segment_255();
    test_segment_maps();
    test_startup(argv[1]);
    test_invalid_melody_startup(argv[2]);
    test_melody_continuity(true, 4);
    test_melody_continuity(false, 4);
    test_melody_continuity(true, 2);
    test_melody_continuity(false, 2);
    puts("PASS: segment 255, clean game startup, continuous SM511 audio");
    return 0;
}

/* Deterministic host diagnostic for the real GameNWatchDS SM5xx core. */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "gw_graphic.h"
#include "gw_romloader.h"
#include "gw_system.h"
#include "sm510.h"

#define TEST_FRAMES 36000L

unsigned int gw_buttons_state = 0;
unsigned int gw_get_buttons(void) { return gw_buttons_state; }

static bool is_sm5a_family(void)
{
    return strncmp(gw_head.cpu_name, ROM_CPU_SM5A, 5) == 0 ||
           strncmp(gw_head.cpu_name, ROM_CPU_SM500, 5) == 0;
}

static int segment_count(void)
{
    unsigned char state[256];
    int on = 0;
    if (is_sm5a_family())
        gw_calc_segment_states_sm5a(state);
    else
        gw_calc_segment_states(state);
    for (int i = 0; i < 256; i++)
        on += state[i] != 0;
    return on;
}

static unsigned int scripted_input(long frame)
{
    static const unsigned int sequence[] = {
        GW_BUTTON_GAME, GW_BUTTON_B, GW_BUTTON_TIME, GW_BUTTON_ALARM,
        GW_BUTTON_LEFT, GW_BUTTON_RIGHT, GW_BUTTON_UP, GW_BUTTON_DOWN,
        GW_BUTTON_A,
        GW_BUTTON_LEFT | GW_BUTTON_A,
        GW_BUTTON_RIGHT | GW_BUTTON_A,
        GW_BUTTON_UP | GW_BUTTON_A,
        GW_BUTTON_DOWN | GW_BUTTON_A,
    };
    const long slot = 120;
    const long scripted_frames =
        (long)(sizeof(sequence) / sizeof(sequence[0])) * slot;
    if (frame < scripted_frames) {
        size_t index = (size_t)(frame / slot);
        return (frame % slot) < 30 ? sequence[index] : 0;
    }

    /* Repeat a deterministic mixture after the explicit common controls. */
    uint32_t value = (uint32_t)((frame - scripted_frames) / 60);
    value = value * 1664525U + 1013904223U;
    if (((frame - scripted_frames) % 60) >= 12)
        return 0;
    return sequence[value % (sizeof(sequence) / sizeof(sequence[0]))];
}

static unsigned char *read_file(const char *path, unsigned int *size)
{
    FILE *file = fopen(path, "rb");
    if (!file) {
        fprintf(stderr, "cannot open %s\n", path);
        return NULL;
    }
    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return NULL;
    }
    long length = ftell(file);
    if (length <= 0 || (unsigned long)length > GW_ROM_MAX_SIZE ||
        fseek(file, 0, SEEK_SET) != 0) {
        fprintf(stderr, "invalid .gnw size: %ld\n", length);
        fclose(file);
        return NULL;
    }
    unsigned char *data = malloc((size_t)length);
    if (!data || fread(data, 1, (size_t)length, file) != (size_t)length) {
        fprintf(stderr, "could not read %s\n", path);
        free(data);
        fclose(file);
        return NULL;
    }
    fclose(file);
    *size = (unsigned int)length;
    return data;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: core_harness <file.gnw>\n");
        return 2;
    }

    unsigned int size = 0;
    unsigned char *rom = read_file(argv[1], &size);
    if (!rom)
        return 1;
    if (!gw_romloader_load(rom, size)) {
        fprintf(stderr, "real .gnw loader rejected %s\n", argv[1]);
        free(rom);
        return 1;
    }
    if (!gw_program || !gw_keyboard || !gw_segments ||
        gw_head.program_size == 0 || gw_head.keyboard_size == 0 ||
        gw_head.segments_pixel_size == 0) {
        fprintf(stderr, "incomplete core configuration\n");
        free(rom);
        return 1;
    }
    if (!gw_system_config()) {
        fprintf(stderr, "unsupported CPU configuration: %.8s\n", gw_head.cpu_name);
        free(rom);
        return 1;
    }

    gw_system_start();
    gw_system_reset();
    gw_system_sound_init();
    memset(gw_readk_count, 0, sizeof(gw_readk_count));
    sm510_unknown_opcode_count = 0;
    sm500_unimplemented_opcode_count = 0;
    sm511_guessed_opcode_count = 0;

    bool visited_pc[65536] = {false};
    unsigned int unique_pc = 0;
    unsigned long lcd_active_frames = 0;
    unsigned long audio_nonzero = 0;
    unsigned int audio_peak = 0;

    for (long frame = 0; frame < TEST_FRAMES; frame++) {
        gw_buttons_state = scripted_input(frame);
        gw_system_run(GW_SYSTEM_CYCLES);
        if (!visited_pc[m_pc]) {
            visited_pc[m_pc] = true;
            unique_pc++;
        }
        if (segment_count() > 0)
            lcd_active_frames++;
        for (size_t i = 0; i < sizeof(gw_audio_buffer); i++) {
            unsigned int sample = gw_audio_buffer[i];
            if (sample != 0)
                audio_nonzero++;
            if (sample > audio_peak)
                audio_peak = sample;
        }
    }

    int failed = 0;
#define REQUIRE(condition, message) do { \
    if (!(condition)) { fprintf(stderr, "FAIL: %s\n", message); failed = 1; } \
} while (0)
    REQUIRE(unique_pc > 1, "program counter did not advance");
    REQUIRE(lcd_active_frames > 0, "LCD never became active");
    REQUIRE(audio_nonzero > 0, "audio remained silent");
    REQUIRE(sm510_unknown_opcode_count == 0, "unknown opcode executed");
    REQUIRE(sm500_unimplemented_opcode_count == 0,
            "unimplemented SM500 opcode executed");

    printf("RESULT cpu=%.8s frames=%ld unique_pc=%u lcd_active=%lu "
           "audio_nonzero=%lu audio_peak=%u unknown_opcodes=%lu "
           "unimplemented_sm500=%lu guessed_sm511=%lu status=%s\n",
           gw_head.cpu_name, TEST_FRAMES, unique_pc, lcd_active_frames,
           audio_nonzero, audio_peak, sm510_unknown_opcode_count,
           sm500_unimplemented_opcode_count, sm511_guessed_opcode_count,
           failed ? "FAIL" : "PASS");
    free(rom);
    return failed ? 1 : 0;
}

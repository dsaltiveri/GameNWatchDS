/*
 * Main menu of the emulator: game list on the bottom screen with scroll.
 * D-pad up/down to move and A to enter.
 * Inside a game, R returns to this menu.
 */
#include <nds.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <dirent.h>

#include "menu.h"
#include "menu_font.h"
#include "games.h"
#include "emulator.h"

/* SD card state (set by menu_set_sd_ok from main). */
static int g_sd_ok = 1;

void menu_set_sd_ok(int ok){ g_sd_ok = ok; }

/* Number of visible games per page in the bottom list. */
#define PAGE_SIZE 11

/* Controls shown on the top screen for each game. */
// (menu_controls removed: the top screen shows the case preview)
#define MENU_CLR_TITLE   (0x8000 | RGB15(31, 31, 31))
#define MENU_CLR_TEXT    (0x8000 | RGB15(28, 28, 28))
#define MENU_CLR_DIM     (0x8000 | RGB15(18, 18, 18))
#define MENU_CLR_SEL     (0x8000 | RGB15(31, 24, 0))
#define MENU_CLR_BAR     (0x8000 | RGB15(9, 9, 9))

/* Framebuffers Bmp16 256x192 (MODE_3_2D). */
static u16 *g_top = NULL;
static u16 *g_bot = NULL;

static void menu_clear(u16 *fb){
    memset(fb, 0, 256 * 192 * sizeof(u16));
}

static void menu_line(u16 *fb, int y, u16 color){
    for (int x = 0; x < 256; x++)
        fb[y * 256 + x] = color;
}

/* Draws a 6x8 glyph (1bpp, bits packed to the left). Glyphs that would not fit
   in the framebuffer are dropped (long paths in the notices). */
static void menu_glyph(u16 *fb, int px, int py, unsigned char ch, u16 color){
    if (px < 0 || px + MENU_FONT_W > 256 || py < 0 || py + MENU_FONT_H > 192)
        return;
    if (ch < 32 || ch > 127) ch = '?';
    const unsigned char *g = menu_font[ch - 32];
    for (int row = 0; row < MENU_FONT_H; row++){
        unsigned char bits = g[row];
        u16 *dst = fb + (py + row) * 256 + px;
        /* The BG3 Bmp16 in MODE_5 shows flipped columns: each glyph is
           drawn horizontally mirrored so it looks correct. */
        for (int col = 0; col < MENU_FONT_W; col++){
            if (bits & (0x20 >> col))
                dst[MENU_FONT_W - 1 - col] = color;
        }
    }
}

/* Fixed-width 6px text; x is the pixel position (left column). */
static void menu_text(u16 *fb, int px, int py, const char *s, u16 color){
    while (*s){
        if (*s == '\n'){
            py += MENU_FONT_H;
            px = 0;
            s++;
            continue;
        }
        menu_glyph(fb, px, py, (unsigned char)*s, color);
        px += MENU_FONT_W;
        s++;
    }
}

/* Horizontally centered text. */
static void menu_text_cx(u16 *fb, int py, const char *s, u16 color){
    int w = 0;
    for (const char *p = s; *p; p++)
        w += MENU_FONT_W;
    menu_text(fb, (256 - w) / 2, py, s, color);
}

#define MENU_VISIBLE 11

/* Indexes of games whose .gnw exists in /gnw/ (built when the menu opens). */
static int g_visible[64];
static int g_visible_count = 0;

/* Auto-scan of /gnw/: walks the directory with opendir/readdir (newlib
   dirent over the SD FAT) and matches each .gnw with its descriptor by
   path. Only games with a descriptor whose .gnw is on the SD are listed
   (a .gnw without a descriptor is unplayable: it lacks the key mapping and
   the render config from game_*.c). */
static void menu_build_visible(void){
    g_visible_count = 0;
    DIR *dir = opendir("/gnw");
    if (!dir) return;
    struct dirent *de;
    while ((de = readdir(dir)) != NULL){
        const char *fname = de->d_name;
        size_t n = strlen(fname);
        if (n < 5 || strcasecmp(fname + n - 4, ".gnw") != 0)
            continue;
        char full[288];
        snprintf(full, sizeof(full), "/gnw/%s", fname);
        for (int i = 0; i < game_count; i++){
            if (strcasecmp(full, games[i]->rom_path) == 0){
                g_visible[g_visible_count++] = i;
                break;
            }
        }
    }
    closedir(dir);

    /* Alphabetical order by display name, regardless of FAT order and
       the order of the games[] array. This way, adding/removing .gnw files
       keeps the list sorted and the first game (g_visible[0], the one
       preselected when the menu opens) is the alphabetically first. */
    for (int i = 1; i < g_visible_count; i++){
        int gi = g_visible[i];
        int j = i - 1;
        while (j >= 0 && strcasecmp(games[g_visible[j]]->name,
                                    games[gi]->name) > 0){
            g_visible[j + 1] = g_visible[j];
            j--;
        }
        g_visible[j + 1] = gi;
    }
}

static void menu_draw(int sel){
    /* --- top screen: unused (black) --- */
    menu_clear(g_top);

    /* --- bottom screen: retro-go style list (centered cursor) --- */
    menu_clear(g_bot);
    char buf[40];
    snprintf(buf, sizeof(buf), "SELECT GAME (%d)", g_visible_count);
    menu_text_cx(g_bot, 3, buf, MENU_CLR_TITLE);
    menu_line(g_bot, 14, MENU_CLR_BAR);

    int lines = MENU_VISIBLE;
    int top = sel - lines / 2;
    /* scroll clamped: up (Ball at the start) and down (last games). */
    if (top < 0) top = 0;
    int max_top = g_visible_count - lines;
    if (max_top < 0) max_top = 0;
    if (top > max_top) top = max_top;
    for (int i = 0; i < lines; i++){
        int entry = top + i;
        if (entry < 0 || entry >= g_visible_count)
            continue;
        int gi = g_visible[entry];
        int y = 20 + i * 14;
        /* clamp to columns so the name does not overflow */
        char name[40];
        snprintf(name, sizeof(name), "%.*s", 34, games[gi]->name);

        if (entry == sel){
            menu_text(g_bot, 4, y, ">", MENU_CLR_SEL);
            menu_text(g_bot, 14, y, name, MENU_CLR_SEL);
        } else {
            menu_text(g_bot, 4, y, name, MENU_CLR_TEXT);
        }
    }

    /* --- footer: separator line above the project name, mirroring the header
       (title text on top, bar below it; here bar above the footer text) --- */
    menu_line(g_bot, 177, MENU_CLR_BAR);
    menu_text_cx(g_bot, 181, "GAME & WATCH EMULATOR DS V0.1", MENU_CLR_TEXT);
}

int menu_select(int preselect){
    /* Bmp16 framebuffer on both screens (redone when returning from a game).
       Same pattern as emulator_init: MODE_5_2D + bgInit + videoBgEnable. */
    powerOn(POWER_ALL_2D);
    videoSetMode(MODE_5_2D);
    videoSetModeSub(MODE_5_2D);

    vramSetBankA(VRAM_A_MAIN_BG);
    vramSetBankC(VRAM_C_SUB_BG);

    bgInit(3, BgType_Bmp16, BgSize_B16_256x256, 0, 0);
    bgInitSub(3, BgType_Bmp16, BgSize_B16_256x256, 0, 0);
    videoBgEnable(3);
    videoBgEnableSub(3);

    g_top = BG_GFX;
    g_bot = BG_GFX_SUB;

    /* Detect which games have a .gnw in /gnw/ and navigate over those. */
    menu_build_visible();
    if (g_visible_count == 0){
        menu_clear(g_bot);
        menu_text_cx(g_bot, 60, "NO GAMES", MENU_CLR_TITLE);
        menu_text_cx(g_bot, 84, "COPY THE .GNW FILES TO /gnw/", MENU_CLR_TEXT);
        while (1){
            swiWaitForVBlank();
            scanKeys();
            if (keysDown() & (KEY_A | KEY_B | KEY_START))
                return -1;
        }
    }

    int sel = 0;
    if (preselect >= 0){
        /* Preselect the last played game (global index in games[]). If it is
           no longer visible (e.g. its .gnw was deleted) the first is kept. */
        for (int i = 0; i < g_visible_count; i++){
            if (g_visible[i] == preselect){ sel = i; break; }
        }
    }
    menu_draw(sel);

    /* auto-repeat with acceleration: while the d-pad is held up/down the
       movement repeats; the interval between repeats shrinks progressively
       down to a functional minimum. */
    int delay0 = 26;    /* frames until the first repeat */
    int rate0  = 12;    /* frames between repeats (initial) */
    int rate_min = 2;   /* minimum frames (speed cap) */
    int cur_dir = 0;    /* held direction (-1 = up, +1 = down) */
    int next = delay0;  /* frames until the next repeat */
    int rate = rate0;

    for (;;){
        swiWaitForVBlank();
        scanKeys();
        u32 down = keysDown();
        u32 held = keysHeld();

        int dir = 0;
        if (held & KEY_UP) dir = -1;
        else if (held & KEY_DOWN) dir = 1;

        if (dir != 0 && dir != cur_dir){
            /* fresh press or direction change: move 1 and reset */
            sel = (sel + dir + g_visible_count) % g_visible_count;
            menu_draw(sel);
            cur_dir = dir;
            next = delay0;
            rate = rate0;
        } else if (dir != 0){
            /* same held direction: auto-repeat with acceleration */
            if (--next <= 0){
                sel = (sel + dir + g_visible_count) % g_visible_count;
                menu_draw(sel);
                rate = (rate > rate_min) ? (rate - 1) : rate_min;
                next = rate;
            }
        } else {
            cur_dir = 0;
            next = delay0;
            rate = rate0;
        }

        if (down & KEY_A){
            return g_visible[sel];
        }
    }
}

/* ---- notices (errors and direct launch) ----
   Both screens as Bmp16 (MODE_5_2D): emulator_run() leaves the video mode and
   the VRAM banks configured, so they are set up again here. */

static void notice_begin(void){
    powerOn(POWER_ALL_2D);
    videoSetMode(MODE_5_2D);
    videoSetModeSub(MODE_5_2D);

    vramSetBankA(VRAM_A_MAIN_BG);
    vramSetBankC(VRAM_C_SUB_BG);

    bgInit(3, BgType_Bmp16, BgSize_B16_256x256, 0, 0);
    bgInitSub(3, BgType_Bmp16, BgSize_B16_256x256, 0, 0);
    videoBgEnable(3);
    videoBgEnableSub(3);

    g_top = BG_GFX;
    g_bot = BG_GFX_SUB;
}

/* Waits for a key (A, B or START) before returning. */
static void notice_wait(void){
    while (1){
        swiWaitForVBlank();
        scanKeys();
        if (keysDown() & (KEY_A | KEY_B | KEY_START))
            return;
    }
}

/* Path shortened to the width of the bottom screen (42 columns of 6 px),
   keeping the end, which is the file name. */
#define NOTICE_PATH_COLS 42
static const char *notice_path(const char *path){
    static char fit[NOTICE_PATH_COLS + 1];
    size_t len = strlen(path);
    if (len <= NOTICE_PATH_COLS)
        snprintf(fit, sizeof(fit), "%s", path);
    else
        snprintf(fit, sizeof(fit), "...%s", path + len - (NOTICE_PATH_COLS - 3));
    return fit;
}

void menu_show_notice(const char *title, const char *path, const char *hint,
                      const char *footer){
    notice_begin();

    menu_clear(g_bot);
    menu_text_cx(g_bot, 40, title, MENU_CLR_TITLE);
    menu_line(g_bot, 50, MENU_CLR_BAR);
    menu_text(g_bot, 20, 78, notice_path(path), MENU_CLR_SEL);
    menu_text(g_bot, 20, 96, hint, MENU_CLR_TEXT);
    menu_text_cx(g_bot, 184, footer, MENU_CLR_SEL);
    notice_wait();
}

void menu_show_error(const char *msg){
    menu_show_notice("COULD NOT LOAD", msg, "COPY THE .GNW INTO THE /gnw/ FOLDER",
                     "A: BACK TO THE MENU");
}

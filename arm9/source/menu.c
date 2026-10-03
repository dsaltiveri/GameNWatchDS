/*
 * Main menu of the emulator: game list on the bottom screen with scroll.
 * D-pad up/down to move and A to enter.
 * Inside a game, R returns to this menu.
 *
 * The menu is drawn with the plain text console of libnds (consoleDemoInit +
 * printf), the same way RetroFabDS does it: no framebuffer, no custom font.
 */
#include <nds.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <dirent.h>

#include "menu.h"
#include "games.h"
#include "emulator.h"

/* SD card state (set by menu_set_sd_ok from main). */
static int g_sd_ok = 1;

void menu_set_sd_ok(int ok){ g_sd_ok = ok; }

/* Console geometry: the libnds font is 8x8 on a 256x192 screen, so the window
   holds 32x24 characters. The last column is never used: a row filled up to
   column 32 wraps to the next line and would scroll the whole menu up. */
#define MENU_TEXT_COLS   31
#define MENU_SCREEN_ROWS 24

/* Games listed at once: the list keeps the selection centered and leaves the
   last row of the window blank (bottom margin). */
#define MENU_LIST_ROWS   19

/* Row (0..MENU_SCREEN_ROWS-1) where the next menu_row() writes. */
static int g_screen_row;

/* Clears the window and puts the cursor at (0,0) so the next menu_row() writes
   the first row again. Needed on every redraw: after a full window the cursor
   is left on the last row. */
static void menu_screen_reset(void){
    printf("\x1b[2J");
    g_screen_row = 0;
}

/* Sets up the text console on the bottom screen, like RetroFabDS:
   consoleDemoInit() configures MODE_0_2D + VRAM_C + BG0 there. The top screen
   is blanked because after a game it still shows the artwork of the last one. */
static void menu_console_begin(void){
    powerOn(POWER_ALL_2D);
    videoSetMode(MODE_0_2D);
    consoleDemoInit();

    consoleSetColor(NULL, CONSOLE_WHITE);
    menu_screen_reset();
}

/* Writes one row of the window (printf style), padded to MENU_TEXT_COLS so a
   shorter row does not leave the tail of the previous one on screen. Rows
   beyond the window are dropped: printing them would scroll the menu up. */
static void menu_row(const char *fmt, ...){
    if (g_screen_row >= MENU_SCREEN_ROWS)
        return;

    char text[MENU_TEXT_COLS + 1];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(text, sizeof(text), fmt, ap);
    va_end(ap);

    if (g_screen_row > 0)
        putchar('\n');
    printf("%-*s", MENU_TEXT_COLS, text);
    g_screen_row++;
}

/* Row with the text centered in the window. */
static void menu_row_center(const char *s){
    int len = (int)strlen(s);
    if (len > MENU_TEXT_COLS)
        len = MENU_TEXT_COLS;

    char text[MENU_TEXT_COLS + 1];
    int pad = (MENU_TEXT_COLS - len) / 2;
    memset(text, ' ', (size_t)pad);
    memcpy(text + pad, s, (size_t)len);
    text[pad + len] = '\0';

    menu_row("%s", text);
}

/* Row, or rows, of a text longer than the window: broken on spaces. */
static void menu_row_wrap(const char *s){
    char text[MENU_TEXT_COLS + 1];

    while (*s){
        size_t len = strlen(s);
        if (len <= MENU_TEXT_COLS){
            menu_row("%s", s);
            return;
        }

        int cut = MENU_TEXT_COLS;
        while (cut > 1 && s[cut] != ' ')
            cut--;
        if (s[cut] != ' ')
            cut = MENU_TEXT_COLS;   /* no space available: cut where it fits */

        memcpy(text, s, (size_t)cut);
        text[cut] = '\0';
        menu_row("%s", text);

        s += cut;
        while (*s == ' ')
            s++;
    }
}

/* Horizontal bar used as separator. */
static void menu_row_bar(void){
    menu_row("%s", "------------------------------");
}

/* Empty rows up to (and not including) the given one. */
static void menu_rows_to(int row){
    while (g_screen_row < row)
        menu_row("");
}

/* Indexes of games whose .gnw exists in /gnw/ (built when the menu opens). */
static int g_visible[GAME_COUNT];
static int g_visible_count = 0;

/* Auto-scan of /gnw/: walks the directory with opendir/readdir (newlib
   dirent over the SD FAT) and matches each .gnw with its descriptor by
   path. Only games with a descriptor whose .gnw is on the SD are listed
   (a .gnw without a descriptor is unplayable: it lacks the key mapping and
   the render config from game_*.c). */
static void menu_build_visible(void){
    g_visible_count = 0;
    bool seen[GAME_COUNT] = {false};
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
                if (!seen[i] && g_visible_count < GAME_COUNT){
                    g_visible[g_visible_count++] = i;
                    seen[i] = true;
                }
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

/* Redraws the whole window: header and list. The names are pegged to the left
   column, so the selected game is marked with another color instead of a
   cursor character (that would move its text to the right). The list stops one
   row before the bottom, which stays blank. */
static void menu_draw(int sel){
    menu_screen_reset();

    consoleSetColor(NULL, CONSOLE_WHITE);
    menu_row_center("GAME & WATCH EMULATOR DS");
    menu_row_bar();
    menu_row("SELECT GAME (%d)", g_visible_count);
    menu_row("");           /* blank line between the header and the list */

    int lines = MENU_LIST_ROWS;
    int top = sel - lines / 2;
    /* scroll clamped: up (Ball at the start) and down (last games). */
    if (top < 0) top = 0;
    int max_top = g_visible_count - lines;
    if (max_top < 0) max_top = 0;
    if (top > max_top) top = max_top;
    for (int i = 0; i < lines; i++){
        int entry = top + i;
        if (entry < 0 || entry >= g_visible_count){
            consoleSetColor(NULL, CONSOLE_WHITE);
            menu_row("");
            continue;
        }
        /* clamp to columns so the name does not overflow */
        consoleSetColor(NULL, (entry == sel) ? CONSOLE_LIGHT_YELLOW : CONSOLE_WHITE);
        menu_row("%.31s", games[g_visible[entry]]->name);
    }

    consoleSetColor(NULL, CONSOLE_WHITE);
}

int menu_select(int preselect){
    /* Text console on the bottom screen (redone when returning from a game,
       whose MODE_5_2D setup has both screens configured by then). */
    menu_console_begin();

    /* Detect which games have a .gnw in /gnw/ and navigate over those. */
    menu_build_visible();
    if (g_visible_count == 0){
        menu_row_center("GAME & WATCH EMULATOR DS");
        menu_row_bar();
        menu_row("");
        menu_row_center("NO GAMES");
        if (g_sd_ok)
            menu_row_center("COPY THE .GNW FILES TO /gnw/");
        else
            menu_row_center("SD CARD COULD NOT BE MOUNTED");
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
   Plain text console too, like the menu: emulator_run() leaves both screens in
   MODE_5_2D, so the console is set up again here. */

/* Waits for a key (A, B or START) before returning. */
static void notice_wait(void){
    while (1){
        swiWaitForVBlank();
        scanKeys();
        if (keysDown() & (KEY_A | KEY_B | KEY_START))
            return;
    }
}

/* Path shortened to the width of a row, keeping the end, which is the file
   name. */
static const char *notice_path(const char *path){
    static char fit[MENU_TEXT_COLS + 1];
    size_t len = strlen(path);
    if (len <= MENU_TEXT_COLS)
        snprintf(fit, sizeof(fit), "%s", path);
    else
        snprintf(fit, sizeof(fit), "...%s", path + len - (MENU_TEXT_COLS - 3));
    return fit;
}

void menu_show_notice(const char *title, const char *path, const char *hint,
                      const char *footer){
    menu_console_begin();

    menu_row_center(title);
    menu_row_bar();
    menu_row("");
    menu_row("%s", notice_path(path));
    menu_row_wrap(hint);

    /* The footer sits at the bottom of the window, like the footer of the
       menu list. */
    menu_rows_to(MENU_SCREEN_ROWS - 1);
    menu_row_center(footer);

    notice_wait();
}

void menu_show_error(const char *msg){
    menu_show_notice("COULD NOT LOAD", msg, "COPY THE .GNW INTO THE /gnw/ FOLDER",
                     "A: BACK TO THE MENU");
}


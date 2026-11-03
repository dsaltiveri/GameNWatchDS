/*
 * Main menu of the emulator: game selection with the D-pad.
 */
#ifndef _MENU_H_
#define _MENU_H_

/* Shows the menu and returns the chosen game index (0..game_count-1).
   preselect: index (global in games[]) of the game to preselect on open,
   or -1 to select the first one in the list. */
int menu_select(int preselect);

/* Actual scanned path for a catalog index, valid until the next menu scan. */
const char *menu_game_path(int index);

/* Advance to the next copy of the same game after a failed load. NULL means
   none remain; the current path is retained so its load error can be shown. */
const char *menu_next_game_path(int index);

/* Shows an error notice (e.g. ROM not found) and waits for a key. */
void menu_show_error(const char *msg);

/* Full-screen notice for the direct launch (the game was opened from a loader
   such as TWiLight Menu++): title, path of the .gnw that failed, a hint line and
   the footer with the key to press. Waits for a key; returning from main() then
   gives the control back to the launcher. */
void menu_show_notice(const char *title, const char *path, const char *hint,
                      const char *footer);

/* Tells the menu whether the SD card could be mounted (to warn the user). */
void menu_set_sd_ok(int ok);

#endif /* _MENU_H_ */

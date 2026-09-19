/*
 * Main menu of the emulator: game selection with the D-pad.
 */
#ifndef _MENU_H_
#define _MENU_H_

/* Shows the menu and returns the chosen game index (0..game_count-1).
   preselect: index (global in games[]) of the game to preselect on open,
   or -1 to select the first one in the list. */
int menu_select(int preselect);

/* Shows an error notice (e.g. ROM not found) and waits for a key. */
void menu_show_error(const char *msg);

/* Tells the menu whether the SD card could be mounted (to warn the user). */
void menu_set_sd_ok(int ok);

#endif /* _MENU_H_ */

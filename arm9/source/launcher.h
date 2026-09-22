/*
 * Direct launch from a file browser/loader (TWiLight Menu++ custom launchers,
 * .argv files, Homebrew Menu...): reads the .gnw path from the command line and
 * normalises its device prefix, so main() can boot the game without the menu.
 */
#ifndef _LAUNCHER_H_
#define _LAUNCHER_H_

#include <stdbool.h>
#include <stddef.h>

/* Longest path handled: ".gnw" path + device prefix ("sd:"/"fat:"). */
#define LAUNCHER_PATH_MAX 288

/* First command line argument naming a .gnw (case-insensitive extension), or
   the first argument that can be opened when none has the extension (loaders
   that drop it). NULL when there is no file argument: the menu is shown. */
const char *launcher_arg_path(int argc, char **argv);

/* Returns a path that can be opened, written into buf, out of these candidates:
   the path itself (a path without a device is resolved by libfat against its
   default drive), the same file on the other device ("sd:" <-> "fat:") and the
   path with the drive of fatGetDefaultDrive() added. NULL when none of them can
   be opened. */
const char *launcher_resolve(const char *path, char *buf, size_t buflen);

/* Reads the CPU name and the ROM signature of a .gnw: the first 16 bytes of its
   header (cpu_name[8] + rom_signature[8], see gw_sys/gw_romloader.h). Both
   output buffers must hold 9 bytes (the header fields are not NUL terminated).
   Returns false when the file cannot be read or is too short. */
bool launcher_read_rom_id(const char *path, char cpu[9], char sig[9]);

#endif /* _LAUNCHER_H_ */
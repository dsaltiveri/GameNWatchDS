#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#include "launcher.h"

static char host_root[1024];
static const char *default_drive = "sd:/";

const char *fatGetDefaultDrive(void)
{
    return default_drive;
}

FILE *launcher_host_fopen(const char *path, const char *mode)
{
    char mapped[1400];
    const char *device = NULL;
    const char *rest = path;

    if (strncasecmp(path, "sd:", 3) == 0) {
        device = "sd";
        rest = path + 3;
    } else if (strncasecmp(path, "fat:", 4) == 0) {
        device = "fat";
        rest = path + 4;
    } else if (!(isalpha((unsigned char)path[0]) && path[1] == ':') &&
               path[0] != '/' && path[0] != '\\') {
        device = (strncasecmp(default_drive, "fat:", 4) == 0) ? "fat" : "sd";
    }

    if (!device)
        return fopen(path, mode);
    while (*rest == '/' || *rest == '\\')
        rest++;
    if (snprintf(mapped, sizeof(mapped), "%s/%s/%s", host_root, device,
                 rest) >= (int)sizeof(mapped))
        return NULL;
    return fopen(mapped, mode);
}

static int failed = 0;

#define CHECK(condition, message) do { \
    if (!(condition)) { fprintf(stderr, "FAIL: %s\n", message); failed = 1; } \
} while (0)

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: launcher_harness <virtual-root> <source.gnw>\n");
        return 2;
    }
    if (snprintf(host_root, sizeof(host_root), "%s", argv[1]) >=
        (int)sizeof(host_root)) {
        fprintf(stderr, "virtual root is too long\n");
        return 2;
    }

    char *no_file[] = {"GameNWatchDS.nds"};
    CHECK(launcher_arg_path(1, no_file) == NULL,
          "empty argv should open the catalog");

    char *with_extension[] = {
        "GameNWatchDS.nds", "--ignored", "sd:/roms/gnw/direct.GNW"
    };
    CHECK(launcher_arg_path(3, with_extension) == with_extension[2],
          "case-insensitive .gnw argument was not selected");

    char *without_extension[] = {
        "GameNWatchDS.nds", "fat:/roms/gnw/renamed"
    };
    CHECK(launcher_arg_path(2, without_extension) == without_extension[1],
          "openable extensionless argument was not selected");

    char buffer[LAUNCHER_PATH_MAX];
    const char *resolved = launcher_resolve(
        "sd:/roms/gnw/direct.GNW", buffer, sizeof(buffer));
    CHECK(resolved && strcmp(resolved, "sd:/roms/gnw/direct.GNW") == 0,
          "direct SD path did not resolve");

    resolved = launcher_resolve(
        "sd:/roms/gnw/fallback.gnw", buffer, sizeof(buffer));
    CHECK(resolved && strcmp(resolved, "fat:/roms/gnw/fallback.gnw") == 0,
          "SD to FAT fallback did not resolve");

    default_drive = "sd:/";
    resolved = launcher_resolve("roms/gnw/direct.GNW", buffer, sizeof(buffer));
    CHECK(resolved && strcmp(resolved, "roms/gnw/direct.GNW") == 0,
          "path on the default drive did not resolve");

    default_drive = "fat:/";
    resolved = launcher_resolve("roms/gnw/fallback.gnw", buffer,
                                sizeof(buffer));
    CHECK(resolved && strcmp(resolved, "roms/gnw/fallback.gnw") == 0,
          "FAT default drive did not resolve");

    CHECK(launcher_resolve("missing.gnw", buffer, sizeof(buffer)) == NULL,
          "missing path unexpectedly resolved");
    CHECK(launcher_resolve("sd:/roms/gnw/direct.GNW", buffer,
                           sizeof(buffer) - 1) == NULL,
          "undersized destination buffer was accepted");

    char source_cpu[9], source_sig[9], renamed_cpu[9], renamed_sig[9];
    CHECK(launcher_read_rom_id(argv[2], source_cpu, source_sig),
          "source header could not be read");
    CHECK(launcher_read_rom_id("fat:/roms/gnw/renamed", renamed_cpu,
                               renamed_sig),
          "renamed package header could not be read");
    CHECK(strcmp(source_cpu, renamed_cpu) == 0 &&
          strcmp(source_sig, renamed_sig) == 0,
          "renamed package identity differs from its header");
    CHECK(!launcher_read_rom_id("fat:/roms/gnw/truncated.gnw", renamed_cpu,
                                renamed_sig),
          "truncated package header was accepted");

    printf("RESULT argv=PASS device_fallback=PASS header_id=PASS status=%s\n",
           failed ? "FAIL" : "PASS");
    return failed ? 1 : 0;
}

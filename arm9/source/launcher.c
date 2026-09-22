/*
 * GameNWatchDS : direct launch from a file browser (TWiLight Menu++, .argv...).
 *
 * TWiLight Menu++ launches a homebrew with the data file as its argument when a
 * custom launcher config (sd:/_nds/TWiLightMenu/extras/config.gnw.ini) names the
 * .gnw extension, the same protocol PicoDriveTWL uses for .md/.gen ROMs. This
 * module reads that argument and normalises its device prefix; main() then boots
 * the game with no menu and gives the control back to the file browser on exit.
 */
#include <nds.h>
#include <fat.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>

#include "launcher.h"

/* True when the path ends in ".gnw" (the extension the loaders pass us). */
static bool has_gnw_extension(const char *path)
{
    size_t len = strlen(path);
    return (len > 4 && strcasecmp(path + len - 4, ".gnw") == 0);
}

/* True when the path can be opened for reading (device included). */
static bool openable(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f)
        return false;
    fclose(f);
    return true;
}

const char *launcher_arg_path(int argc, char **argv)
{
    for (int i = 1; i < argc; i++)
    {
        if (argv[i] && argv[i][0] && has_gnw_extension(argv[i]))
            return argv[i];
    }

    /* Loaders that pass a single argument may drop the extension of the data
       file: in that case argv[1] is the file itself. */
    if (argc > 1 && argv[1] && argv[1][0] && openable(argv[1]))
        return argv[1];

    return NULL;
}

/* Copies path into buf replacing its device with dev (e.g. "sd:"), or adding
   the device when the path has none. Returns NULL when it does not fit. */
static const char *set_device(const char *path, const char *dev,
                              char *buf, size_t buflen)
{
    const char *rest = path;
    const char *colon = strchr(path, ':');
    const char *slash = strchr(path, '/');

    /* A device prefix is a short name followed by ':' before the first '/' */
    if (colon && (!slash || colon < slash))
        rest = colon + 1;

    if (snprintf(buf, buflen, "%s%s", dev, rest) >= (int)buflen)
        return NULL;
    return buf;
}

/* The device the path does not use: on the DS the SD card is "fat:" (DLDI) and
   on the DSi it is "sd:" (both are mounted when a Slot-1 card is inserted). */
static const char *other_device(const char *path)
{
    if (strncasecmp(path, "fat:", 4) == 0)
        return "sd:";
    if (strncasecmp(path, "sd:", 3) == 0)
        return "fat:";
    return NULL;
}

static const char *try_device(const char *path, const char *dev,
                              char *buf, size_t buflen)
{
    if (!set_device(path, dev, buf, buflen))
        return NULL;
    return openable(buf) ? buf : NULL;
}

const char *launcher_resolve(const char *path, char *buf, size_t buflen)
{
    if (!path || !path[0] || !buf || buflen < LAUNCHER_PATH_MAX)
        return NULL;

    /* TWiLight Menu++ passes absolute paths ("sd:/roms/gnw/gnw_dkong.gnw"). */
    if (openable(path))
        return path;

    const char *dev = other_device(path);
    if (dev)
    {
        const char *found = try_device(path, dev, buf, buflen);
        if (found)
            return found;
    }

    /* Without a device prefix the path is tried on the default drive of libfat
       ("sd:/" on a DSi, "fat:/" on a DS) and then on the other one, in case the
       menu passed a path of the device it does not run from. */
    const char *def = fatGetDefaultDrive();
    const char *colon = def ? strchr(def, ':') : NULL;
    if (colon && (size_t)(colon - def) < 8)
    {
        char devbuf[8];
        memcpy(devbuf, def, colon - def + 1);
        devbuf[colon - def + 1] = '\0';

        const char *found = try_device(path, devbuf, buf, buflen);
        if (found)
            return found;

        found = try_device(path, (strcasecmp(devbuf, "sd:") == 0) ? "fat:" : "sd:",
                           buf, buflen);
        if (found)
            return found;
    }

    return NULL;
}

bool launcher_read_rom_id(const char *path, char cpu[9], char sig[9])
{
    /* gwromheader_t starts with cpu_name[8] + rom_signature[8] (see
       gw_sys/gw_romloader.h). Neither field is NUL terminated in the file, so
       both outputs get a terminator here. */
    char head[16];
    FILE *f = fopen(path, "rb");
    if (!f)
        return false;

    size_t n = fread(head, 1, sizeof(head), f);
    fclose(f);
    if (n != sizeof(head))
        return false;

    memcpy(cpu, head, 8);
    cpu[8] = '\0';
    memcpy(sig, head + 8, 8);
    sig[8] = '\0';
    return true;
}
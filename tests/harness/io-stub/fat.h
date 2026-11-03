#ifndef GNW_IO_TEST_FAT_H
#define GNW_IO_TEST_FAT_H
#include <stdbool.h>
static inline bool fatInitDefault(void){return true;}
const char *fatGetDefaultDrive(void);
#endif

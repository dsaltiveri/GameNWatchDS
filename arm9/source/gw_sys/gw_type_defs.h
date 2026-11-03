#ifndef __GW_TYPE_DEFS_H__
#define __GW_TYPE_DEFS_H__

/* LCD-Game-Emulator base types (always defined here) */
typedef unsigned char byte;
typedef unsigned char un8;
typedef unsigned short un16;
typedef unsigned int un32;

typedef signed char n8;
typedef signed short n16;
typedef signed int n32;
typedef un16 word;
typedef word addr;

/* Nintendo DS : libnds/calico already define u8/u16/u32/uint8/uint16/uint32
   as typedefs. Since we cannot use #ifndef with typedefs, we map our
   conveniences with macros (macros can coexist with typedefs in C).
   When libnds is not included yet, these macros expand to our un8/un16/un32. */
#ifndef u8
#define u8 un8
#endif
#ifndef u16
#define u16 un16
#endif
#ifndef u32
#define u32 un32
#endif

#ifndef uint8
#define uint8 un8
#endif
#ifndef uint16
#define uint16 un16
#endif
#ifndef uint32
#define uint32 un32
#endif

#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>

#endif
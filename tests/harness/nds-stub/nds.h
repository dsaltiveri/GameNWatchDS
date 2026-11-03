/* Host stand-ins for DS hardware: only used by run_regression_tests.py. */
#ifndef GNW_TEST_NDS_H
#define GNW_TEST_NDS_H
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int16_t s16;
static u16 host_main_fb[256 * 256], host_sub_fb[256 * 256];
#define BG_GFX host_main_fb
#define BG_GFX_SUB host_sub_fb
static u16 TIMER0_DATA, TIMER1_DATA, TIMER0_CR, TIMER1_CR;
enum { POWER_ALL_2D, MODE_5_2D, VRAM_A_MAIN_BG, VRAM_C_SUB_BG,
       BgType_Bmp16, BgSize_B16_256x256, SoundFormat_16Bit,
       TIMER_ENABLE = 128, TIMER_DIV_1 = 0, TIMER_CASCADE = 4,
       KEY_A = 1, KEY_B = 2, KEY_START = 8, KEY_R = 256, KEY_L = 512 };
static int host_flushed, host_played;
static inline void powerOn(int x) { (void)x; }
static inline void videoSetMode(int x) { (void)x; }
static inline void videoSetModeSub(int x) { (void)x; }
static inline void vramSetBankA(int x) { (void)x; }
static inline void vramSetBankC(int x) { (void)x; }
static inline void bgInit(int a,int b,int c,int d,int e) { (void)a;(void)b;(void)c;(void)d;(void)e; }
#define bgInitSub bgInit
static inline void videoBgEnable(int x) { (void)x; }
#define videoBgEnableSub videoBgEnable
static inline void dmaCopy(const void *a,void *b,int n) { memcpy(b,a,(size_t)n); }
static inline void dmaFillWords(u32 v,void *b,int n) { u32 *p=b; for(int i=0;i<n/4;i++)p[i]=v; }
static inline void consoleDemoInit(void) {}
static inline void swiWaitForVBlank(void) {}
static inline void scanKeys(void) {}
static inline u32 keysDown(void) { return KEY_A; }
static inline u32 keysHeld(void) { return 0; }
static inline void soundEnable(void) {}
static inline void soundDisable(void) {}
static inline void soundKill(int x) { (void)x; }
static inline void DC_FlushRange(const void *p,int n) { (void)p;(void)n;host_flushed=1; }
static inline int soundPlaySample(const void *p,int format,int size,int freq,int vol,int pan,bool loop,int point) {
    (void)p;(void)format;(void)size;(void)freq;(void)vol;(void)pan;(void)loop;(void)point;
    host_played = host_flushed;
    return 0;
}
#endif

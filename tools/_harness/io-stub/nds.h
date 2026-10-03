#ifndef GNW_IO_TEST_NDS_H
#define GNW_IO_TEST_NDS_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef uint32_t u32;
enum {KEY_A=1,KEY_B=2,KEY_SELECT=4,KEY_START=8,KEY_RIGHT=16,KEY_LEFT=32,
      KEY_UP=64,KEY_DOWN=128,KEY_R=256,KEY_L=512,KEY_X=1024,KEY_Y=2048,
      POWER_ALL_2D=0,MODE_0_2D=0,CONSOLE_WHITE=0,CONSOLE_LIGHT_YELLOW=1};
static inline u32 keysHeld(void){return 0;}
static inline u32 keysDown(void){return KEY_A;}
static inline void scanKeys(void){}
static inline void swiWaitForVBlank(void){}
static inline bool isDSiMode(void){return false;}
static inline void setCpuClock(bool on){(void)on;}
static inline void powerOn(int x){(void)x;}
static inline void videoSetMode(int x){(void)x;}
static inline void consoleDemoInit(void){}
static inline void consoleSetColor(void *p,int c){(void)p;(void)c;}
#endif

#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <nds.h>
#include "games.h"
#include "launcher.h"

static const game_desc_t *played;
static int notices, menu_index = -1;
static const char *mounted_path;
FILE *launcher_host_fopen(const char *path,const char *mode){
    return fopen(strcmp(path,game_fire.rom_path)==0 ? mounted_path : path, mode);
}
int emulator_run_path(const game_desc_t *g,const char *path){(void)path;played=g;return 1;}
int emulator_run(const game_desc_t *g){(void)g;return 1;}
int menu_select(int n){(void)n;int result=menu_index;menu_index=-1;return result;}
void menu_set_sd_ok(int n){(void)n;}
void menu_show_error(const char *s){(void)s;}
void menu_show_notice(const char*a,const char*b,const char*c,const char*d){
    (void)a;(void)b;(void)c;(void)d;notices++;
}
const char *fatGetDefaultDrive(void){return "sd:/";}
#define main application_main
#include "../../arm9/source/main.c"
#undef main

enum { IO_OK, IO_OPEN, IO_END, IO_TELL, IO_REWIND, IO_READ };
static int fault, opens, closes, seeks, tells, reads;
static FILE *io_open(const char *p,const char *m){
    if(fault==IO_OPEN)return NULL;
    FILE *f=fopen(p,m);if(f)opens++;return f;
}
static int io_close(FILE *f){closes++;return fclose(f);}
static int io_seek(FILE *f,long off,int origin){
    seeks++;
    if((fault==IO_END && origin==SEEK_END) ||
       (fault==IO_REWIND && origin==SEEK_SET))return -1;
    return fseek(f,off,origin);
}
static long io_tell(FILE *f){tells++;return fault==IO_TELL ? -1 : ftell(f);}
static size_t io_read(void *p,size_t size,size_t count,FILE*f){
    reads++;
    return fread(p,size,fault==IO_READ && count ? count-1 : count,f);
}
#define fopen io_open
#define fclose io_close
#define fseek io_seek
#define ftell io_tell
#define fread io_read
#include "../../arm9/source/gw_sys/gw_romloader.c"
#undef fopen
#undef fclose
#undef fseek
#undef ftell
#undef fread

int main(int argc,char **argv){
    assert(argc==3);
    assert(game_count==GAME_COUNT);
    for(int i=0;i<game_count;i++)
        assert(games_find_by_rom(games[i]->cpu,games[i]->rom_sig)==games[i]);
    assert(games_find_by_rom("SM5A_","w_ball__")==&game_ball);
    assert(games_find_by_rom("SM5A_","w_ball")==NULL);
    assert(games_find_by_rom("SM510","w_ball__")==NULL);
    assert(games_find_by_rom("SM5A_","unknown_")==NULL);
    /* Ball's header stored under Fire's usual filename must still run Ball. */
    char *args[]={"GameNWatchDS.nds",argv[1]};
    assert(games_find_by_file(argv[1])==&game_fire);
    assert(boot_from_loader(2,args));
    assert(played==&game_ball && notices==0);
    mounted_path=argv[1];played=NULL;
    for(int i=0;i<game_count;i++)if(games[i]==&game_fire)menu_index=i;
    char *menu_args[]={"GameNWatchDS.nds"};
    assert(application_main(1,menu_args)==0);
    assert(played==&game_ball);
    /* Unknown headers cannot bypass identification via a familiar filename. */
    FILE *f=fopen(argv[1],"wb");assert(f);
    assert(fwrite("BADCPU__unknown_",1,16,f)==16);fclose(f);
    played=NULL;
    assert(boot_from_loader(2,args));assert(!played && notices==1);
    for(fault=IO_OPEN;fault<=IO_READ;fault++){
        opens=closes=seeks=tells=reads=0;
        assert(!gw_romloader_load_file(argv[2]));
        assert(opens==closes);
        if(fault==IO_OPEN)assert(seeks==0 && tells==0 && reads==0);
        if(fault==IO_END)assert(seeks==1 && tells==0 && reads==0);
        if(fault==IO_TELL)assert(seeks==1 && tells==1 && reads==0);
        if(fault==IO_REWIND)assert(seeks==2 && tells==1 && reads==0);
        if(fault==IO_READ)assert(reads==1);
    }
    fault=IO_OK;assert(gw_romloader_load_file(argv[2]));
    assert(opens==closes);
    puts("PASS: header identity, strict signatures, file I/O failures");
}

#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <nds.h>
#include "games.h"
#include "launcher.h"

static const game_desc_t *played;
static int fail_run;
static int notices, menu_index = -1;
static const char *mounted_path;
static const char *alternative_path;
static const char *scan_path;
static int run_attempts;
static char last_hint[160];
const char *menu_game_path(int index){(void)index;return mounted_path;}
const char *menu_next_game_path(int index){
    (void)index;
    const char *next=alternative_path;
    alternative_path=NULL;
    if(scan_path){char cpu[9],sig[9];launcher_read_rom_id(scan_path,cpu,sig);}
    return next;
}
FILE *launcher_host_fopen(const char *path,const char *mode){
    return fopen(strcmp(path,game_fire.rom_path)==0 ? mounted_path : path, mode);
}
int emulator_run_path(const game_desc_t *g,const char *path){
    run_attempts++;
    if(fail_run && !gw_romloader_load_file(path))return 0;
    played=g;return 1;
}
int emulator_run(const game_desc_t *g){(void)g;return 1;}
int menu_select(int n){(void)n;int result=menu_index;menu_index=-1;return result;}
void menu_set_sd_ok(int n){(void)n;}
void menu_show_error(const char *s){(void)s;}
void menu_show_notice(const char*a,const char*b,const char*c,const char*d){
    (void)a;(void)b;(void)d;snprintf(last_hint,sizeof(last_hint),"%s",c);notices++;
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

static void assert_no_loaded_rom(void){
    assert(!gw_program && !gw_melody && !gw_keyboard && !gw_segments);
    assert(!gw_segments_x && !gw_segments_y && !gw_segments_width);
    assert(!gw_segments_height && !gw_segments_offset);
    assert(!gw_rom_backdrop(0) && !gw_rom_backdrop(1));
    assert(gw_head.cpu_name[0]==0);
}

static void test_melody_validation(const char *path){
    FILE *f=fopen(path,"rb");assert(f);
    assert(fseek(f,0,SEEK_END)==0);long size=ftell(f);assert(size>0);rewind(f);
    unsigned char *rom=malloc((size_t)size+256);assert(rom);
    assert(fread(rom,1,(size_t)size,f)==(size_t)size);fclose(f);
    gwromheader_t *header=(gwromheader_t *)rom;
    /* Both melody CPUs must reject an otherwise structurally valid package. */
    for(int cpu=511;cpu<=512;cpu++){
        memcpy(header->cpu_name,cpu==511 ? "SM511___" : "SM512___",8);
        assert(!gw_romloader_load(rom,(unsigned int)size));
        assert(gw_romloader_error()==GW_LOAD_INVALID);assert_no_loaded_rom();
    }
    unsigned int background=header->background_pixel;
    memmove(rom+background+256,rom+background,(size_t)size-background);
    memset(rom+background,2,256);
    header->melody=background;header->melody_size=256;
    header->background_pixel+=256;
    for(int cpu=511;cpu<=512;cpu++){
        memcpy(header->cpu_name,cpu==511 ? "SM511___" : "SM512___",8);
        assert(gw_romloader_load(rom,(unsigned int)size+256));
        assert(gw_rom_backdrop(0)==rom+header->background_pixel);
        assert(gw_romloader()); /* Reload the actual source, including memory packages. */
        for(int bad=0;bad<3;bad++){
            rom[background]=bad==0 ? 0x40 : bad==1 ? 0x0e : 0x0f;
            assert(!gw_romloader_load(rom,(unsigned int)size+256));
            assert(gw_romloader_error()==GW_LOAD_INVALID);assert_no_loaded_rom();
            rom[background]=2;
        }
    }
    free(rom);
    assert(!gw_romloader_load(NULL,0));assert_no_loaded_rom();
}

int main(int argc,char **argv){
    assert(argc==3);
    int prior_notices;
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
    assert(strstr(last_hint,"NOT IN THE EMULATOR CATALOG")!=NULL);
    f=fopen(argv[1],"wb");assert(f);fputs("short",f);fclose(f);
    assert(boot_from_loader(2,args));
    assert(strstr(last_hint,"INVALID FORMAT")!=NULL);
    /* A failed header read keeps its cause even if an alternative scan reads
       another valid header and resets launcher_rom_error() to GW_LOAD_OK. */
    f=fopen(argv[1],"wb");assert(f);fputs("short",f);fclose(f);
    scan_path=argv[2];menu_index=0;prior_notices=notices;
    assert(application_main(1,menu_args)==0);
    assert(notices==prior_notices+1 && strstr(last_hint,"INVALID FORMAT")!=NULL);
    scan_path=NULL;
    for(fault=IO_OPEN;fault<=IO_READ;fault++){
        int requested=fault;fault=IO_OK;
        assert(gw_romloader_load_file(argv[2]));
        fault=requested;
        opens=closes=seeks=tells=reads=0;
        assert(!gw_romloader_load_file(argv[2]));
        assert(gw_romloader_error()==(fault==IO_OPEN ? GW_LOAD_OPEN_ERROR : GW_LOAD_READ_ERROR));
        assert_no_loaded_rom();
        assert(opens==closes);
        if(fault==IO_OPEN)assert(seeks==0 && tells==0 && reads==0);
        if(fault==IO_END)assert(seeks==1 && tells==0 && reads==0);
        if(fault==IO_TELL)assert(seeks==1 && tells==1 && reads==0);
        if(fault==IO_REWIND)assert(seeks==2 && tells==1 && reads==0);
        if(fault==IO_READ)assert(reads==1);
    }
    fault=IO_OK;assert(gw_romloader_load_file(argv[2]));
    assert(gw_romloader_error()==GW_LOAD_OK);
    assert(opens==closes);
    test_melody_validation(argv[2]);
    /* A truncated duplicate must not prevent playing the valid copy. */
    f=fopen(argv[1],"wb");assert(f);
    assert(fwrite("SM5A____w_ball__",1,16,f)==16);fclose(f);
    mounted_path=argv[1];alternative_path=argv[2];menu_index=0;
    played=NULL;fail_run=1;run_attempts=0;prior_notices=notices;
    assert(application_main(1,menu_args)==0);
    assert(played==&game_ball && run_attempts==2 && notices==prior_notices);
    /* Exhausted alternatives produce one notice and do not loop forever. */
    alternative_path=NULL;menu_index=0;played=NULL;run_attempts=0;
    assert(application_main(1,menu_args)==0);
    assert(!played && run_attempts==1 && notices==prior_notices+1);
    assert(strstr(last_hint,"INVALID FORMAT")!=NULL);
    /* Rendered notices preserve the cause reported by the full loader. */
    fail_run=1;args[1]=argv[2];fault=IO_READ;
    assert(boot_from_loader(2,args));assert(strstr(last_hint,"COULD NOT READ")!=NULL);
    fault=IO_OK;
    f=fopen(argv[2],"r+b");assert(f);
    gwromheader_t header;assert(fread(&header,1,sizeof(header),f)==sizeof(header));
    header.program_size=1;rewind(f);assert(fwrite(&header,1,sizeof(header),f)==sizeof(header));fclose(f);
    assert(boot_from_loader(2,args));assert(strstr(last_hint,"INVALID FORMAT")!=NULL);
    puts("PASS: header identity, clean failed loads, melody validation and duplicate fallback");
}

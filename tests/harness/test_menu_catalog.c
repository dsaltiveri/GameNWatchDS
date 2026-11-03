#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <nds.h>
#include "games.h"
#include "dirent.h"
#include "launcher.h"
static const char *package_dir;
const char *fatGetDefaultDrive(void){return "sd:/";}
FILE *launcher_host_fopen(const char *path,const char *mode){
    char full[512];
    snprintf(full,sizeof(full),"%s/%s",package_dir,strrchr(path,'/')+1);
    return fopen(full,mode);
}
static int cursor;
static struct dirent entry;
static DIR *test_opendir(const char *path){(void)path;cursor=0;return (DIR *)&cursor;}
static struct dirent *test_readdir(DIR *dir){
    (void)dir;
    /* Twice each name: repeated/case-alias directory entries are deduplicated. */
    if(cursor>=game_count*2)return NULL;
    snprintf(entry.d_name,sizeof(entry.d_name),"%c_renamed_%03d.gnw",cursor%2 ? 'a' : 'z',cursor/2);
    cursor++;return &entry;
}
static int test_closedir(DIR *dir){(void)dir;return 0;}
#define opendir test_opendir
#define readdir test_readdir
#define closedir test_closedir
#include "menu.c"
#define fopen launcher_host_fopen
#include "../../arm9/source/gw_sys/gw_romloader.c"
#undef fopen
int main(int argc,char **argv){
    assert(argc==3);package_dir=argv[1];
    for(int i=0;i<game_count;i++) for(int alias=0;alias<2;alias++){
        char path[512];snprintf(path,sizeof(path),"%s/%c_renamed_%03d.gnw",package_dir,alias ? 'a' : 'z',i);
        FILE *f=fopen(path,"wb");assert(f);
        char head[16]={0};memcpy(head,games[i]->cpu,strlen(games[i]->cpu));
        memcpy(head+8,games[i]->rom_sig,8);
        assert(fwrite(head,1,16,f)==16);fclose(f);
    }
    assert(GAME_COUNT>64 && game_count==GAME_COUNT);
    menu_build_visible();assert(g_visible_count==game_count);
    bool seen[GAME_COUNT]={false};
    for(int i=0;i<g_visible_count;i++){
        assert(g_visible[i]>=0 && g_visible[i]<game_count);
        assert(!seen[g_visible[i]]);seen[g_visible[i]]=true;
        char expected[64];snprintf(expected,sizeof(expected),"/gnw/a_renamed_%03d.gnw",g_visible[i]);
        assert(strcmp(menu_game_path(g_visible[i]),expected)==0);
        if(i)assert(strcasecmp(games[g_visible[i-1]]->name,games[g_visible[i]]->name)<=0);
    }
    /* The actual menu scans past a truncated first copy to a valid second one. */
    FILE *source=fopen(argv[2],"rb");assert(source);
    assert(fseek(source,0,SEEK_END)==0);long size=ftell(source);assert(size>0);rewind(source);
    unsigned char *rom=malloc((size_t)size);assert(rom);
    assert(fread(rom,1,(size_t)size,source)==(size_t)size);fclose(source);
    memset(rom,0,16);memcpy(rom,games[0]->cpu,strlen(games[0]->cpu));
    memcpy(rom+8,games[0]->rom_sig,8);
    char valid_path[512];snprintf(valid_path,sizeof(valid_path),"%s/z_renamed_000.gnw",package_dir);
    FILE *valid=fopen(valid_path,"wb");assert(valid);
    assert(fwrite(rom,1,(size_t)size,valid)==(size_t)size);fclose(valid);free(rom);
    assert(!gw_romloader_load_file(menu_game_path(0)));
    assert(strcmp(menu_next_game_path(0),"/gnw/z_renamed_000.gnw")==0);
    assert(gw_romloader_load_file(menu_game_path(0)));
    assert(menu_next_game_path(0)==NULL);
    assert(strcmp(menu_game_path(0),"/gnw/z_renamed_000.gnw")==0);
    assert(menu_next_game_path(-1)==NULL && menu_next_game_path(GAME_COUNT)==NULL);
    assert(!gw_romloader_load_file(menu_game_path(1)));
    assert(menu_next_game_path(1)!=NULL);
    assert(!gw_romloader_load_file(menu_game_path(1)));
    assert(menu_next_game_path(1)==NULL);
    /* Invalid and unknown headers are excluded, and stale paths are cleared. */
    for(int i=0;i<2;i++) for(int alias=0;alias<2;alias++){
        char path[512];snprintf(path,sizeof(path),"%s/%c_renamed_%03d.gnw",package_dir,
                              alias ? 'a' : 'z',i);
        FILE *f=fopen(path,"wb");assert(f);
        fputs(i ? "SM5A____unknown_" : "short",f);fclose(f);
    }
    menu_build_visible();assert(g_visible_count==game_count-2);
    assert(menu_game_path(0)==NULL && menu_game_path(1)==NULL);
    assert(menu_next_game_path(0)==NULL && menu_next_game_path(1)==NULL);
    assert(menu_game_path(-1)==NULL && menu_game_path(GAME_COUNT)==NULL);
    puts("PASS: expanded catalog, sorted duplicates and valid-copy fallback");
}

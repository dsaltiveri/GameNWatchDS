#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <nds.h>
#include "games.h"
#include "dirent.h"
static int cursor;
static struct dirent entry;
static DIR *test_opendir(const char *path){(void)path;cursor=0;return (DIR *)&cursor;}
static struct dirent *test_readdir(DIR *dir){
    (void)dir;
    /* Twice each name: repeated/case-alias directory entries are deduplicated. */
    if(cursor>=game_count*2)return NULL;
    const char *name=strrchr(games[cursor/2]->rom_path,'/');
    snprintf(entry.d_name,sizeof(entry.d_name),"%s",name+1);cursor++;return &entry;
}
static int test_closedir(DIR *dir){(void)dir;return 0;}
#define opendir test_opendir
#define readdir test_readdir
#define closedir test_closedir
#include "menu.c"
int main(void){
    assert(GAME_COUNT>64 && game_count==GAME_COUNT);
    menu_build_visible();assert(g_visible_count==game_count);
    bool seen[GAME_COUNT]={false};
    for(int i=0;i<g_visible_count;i++){
        assert(g_visible[i]>=0 && g_visible[i]<game_count);
        assert(!seen[g_visible[i]]);seen[g_visible[i]]=true;
        if(i)assert(strcasecmp(games[g_visible[i-1]]->name,games[g_visible[i]]->name)<=0);
    }
    puts("PASS: expanded catalog above 64 entries, sorted and deduplicated");
}

#!/usr/bin/env python3
"""Builds GameNWatchDS (Game & Watch emulator for DS) with BlocksDS (Wonderful/MSYS2),
syncs the regenerated .gnw to the melonDS virtual SD (/gnw/) and launches
melonDS with the .nds."""
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GNW_DIR = os.path.join(HERE, "shrinker", "output", "gnw")  # output of shrinker/shrink_gnw.py
MAKE = "C:/msys64/usr/bin/make.exe"
MELONDS = "C:/melonDS/melonDS.exe"
SD_DIR = "C:/melonDS/SD"
GW_FILES = ("gnw_ball.gnw", "gnw_fires.gnw", "gnw_vermin.gnw", "gnw_helmet.gnw", "gnw_octopus.gnw", "gnw_pchute.gnw", "gnw_popeye.gnw", "gnw_popeyep.gnw", "gnw_chef.gnw", "gnw_egg.gnw", "gnw_flagman.gnw", "gnw_judge.gnw", "gnw_lion.gnw", "gnw_manholeg.gnw", "gnw_mmouse.gnw", "gnw_mmousep.gnw", "gnw_dkjr.gnw", "gnw_dkjrp.gnw", "gnw_dkcirc.gnw", "gnw_fireatk.gnw", "gnw_manhole.gnw", "gnw_mariocm.gnw", "gnw_mariocmt.gnw", "gnw_stennis.gnw", "gnw_snoopyp.gnw", "gnw_tbridge.gnw", "gnw_tfish.gnw", "gnw_bfightn.gnw", "gnw_climbern.gnw", "gnw_mariotj.gnw", "gnw_mbaway.gnw", "gnw_dkong.gnw", "gnw_ghouse.gnw", "gnw_opanic.gnw", "gnw_squish.gnw", "gnw_bjack.gnw", "gnw_bsweep.gnw", "gnw_gcliff.gnw", "gnw_pinball.gnw", "gnw_sbuster.gnw", "gnw_zelda.gnw", "gnw_mario.gnw", "gnw_rshower.gnw", "gnw_dkong2.gnw", "gnw_fire.gnw", "gnw_lboat.gnw", "gnw_mickdon.gnw", "gnw_smbn.gnw", "gnw_bfight.gnw", "gnw_boxing.gnw", "gnw_cgrab.gnw", "gnw_climber.gnw", "gnw_dkhockey.gnw", "gnw_dkong3.gnw", "gnw_smb.gnw", "gnw_ssparky.gnw")
NDS_PATH = os.path.join(HERE, "GameNWatchDS.nds")

env = dict(os.environ)
# BlockDS/Wonderful toolchain
env["BLOCKSDS"] = "C:/msys64/opt/blocksds/core"
env["BLOCKSDSEXT"] = "C:/msys64/opt/blocksds/external"
env["WONDERFUL_TOOLCHAIN"] = "C:/msys64/opt/wonderful"
env["PATH"] = (
    "C:/msys64/usr/bin"
    + os.pathsep + "C:/msys64/opt/wonderful/toolchain/gcc-arm-none-eabi/bin"
    + os.pathsep + "C:/msys64/opt/wonderful/bin"
    + os.pathsep + env.get("PATH", "")
)


def run(args):
    r = subprocess.run(args, cwd=HERE, env=env, capture_output=True, text=True)
    print("RC", r.returncode)
    if r.stdout:
        print(r.stdout[-4000:])
    if r.stderr:
        print(r.stderr[-4000:])
    return r.returncode


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_gw():
    """Regenerates the .gnw files in gnw/ with shrinker/shrink_gnw.py if any is missing
    (e.g. after a manual wipe of shrinker/output/gnw/). Uses the shrinker/build cache; if there is no
    cache it requires Inkscape (only once)."""
    missing = [n for n in GW_FILES
               if not os.path.isfile(os.path.join(GNW_DIR, n))]
    if not missing:
        return True
    print("GW missing in gnw/: %s -> regenerating with shrinker/shrink_gnw.py"
          % ", ".join(missing))
    script = os.path.join(HERE, "shrinker", "shrink_gnw.py")
    r = subprocess.run([sys.executable, script], cwd=HERE, env=env,
                       capture_output=True, text=True)
    print("RC", r.returncode)
    if r.stdout:
        print(r.stdout[-3000:])
    if r.stderr:
        print(r.stderr[-3000:])
    still = [n for n in GW_FILES
             if not os.path.isfile(os.path.join(GNW_DIR, n))]
    if still:
        print("WARNING: .gnw still missing in gnw/: %s" % ", ".join(still))
        return False
    return True


def sync_sd():
    """Copies the .gnw, the .png case previews and the compiled GameNWatchDS.nds
    to the melonDS virtual SD, only if they are missing or differ (the emulator
    loads the keyboard table from the .gnw and the menu the previews from the
    .png; the .nds goes to the SD root to launch it from the flashcart menu)."""
    src_dir = GNW_DIR
    dst_dir = os.path.join(SD_DIR, "gnw")
    os.makedirs(dst_dir, exist_ok=True)
    print("SYNC SD:", dst_dir)
    for name in GW_FILES:
        src = os.path.join(src_dir, name)
        dst = os.path.join(dst_dir, name)
        if not os.path.isfile(src):
            print("  %-18s MISSING in gnw/" % name)
            continue
        if os.path.isfile(dst) and sha256(src) == sha256(dst):
            print("  %-18s ok (same)" % name)
        else:
            shutil.copy2(src, dst)
            print("  %-18s copied" % name)

    # CASE previews (shrinker/build_gnw_case.py) -> /gnw/case/ (subfolder; the
    # menu decodes them with stb_image, replacing .gnw by .png)
    case_src = os.path.join(src_dir, "case")
    case_dir = os.path.join(dst_dir, "case")
    os.makedirs(case_dir, exist_ok=True)
    for name in sorted(os.listdir(case_src)):
        if not name.endswith(".png"):
            continue
        src = os.path.join(case_src, name)
        dst = os.path.join(case_dir, name)
        if os.path.isfile(dst) and sha256(src) == sha256(dst):
            print("  %-24s ok (same)" % name)
        else:
            shutil.copy2(src, dst)
            print("  %-24s copied" % name)

    # Compiled .nds -> SD root (so the flashcart/melonDS menu runs the
    # emulator straight from the synced card)
    if os.path.isfile(NDS_PATH):
        dst_nds = os.path.join(SD_DIR, os.path.basename(NDS_PATH))
        if os.path.isfile(dst_nds) and sha256(NDS_PATH) == sha256(dst_nds):
            print("  %-24s ok (same)" % os.path.basename(NDS_PATH))
        else:
            shutil.copy2(NDS_PATH, dst_nds)
            print("  %-24s copied" % os.path.basename(NDS_PATH))
    else:
        print("  %-24s MISSING (run make first)" % os.path.basename(NDS_PATH))


def launch_emulator():
    if not os.path.isfile(MELONDS):
        print("MELONDS NOT FOUND:", MELONDS)
        return
    if not os.path.isfile(NDS_PATH):
        print("NDS NOT FOUND:", NDS_PATH)
        return
    print("LAUNCH melonDS:", NDS_PATH)
    try:
        subprocess.Popen([MELONDS, NDS_PATH], cwd=os.path.dirname(MELONDS))
    except Exception as e:
        print("LAUNCH ERROR:", e)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        run([MAKE, "clean"])
    else:
        run([MAKE, "clean"])
        # COMPDB=1 generates compile_commands.json (needed by clangd)
        rc = run([MAKE, "COMPDB=1"])
        print("NDS_EXISTS:", os.path.exists(NDS_PATH),
              os.path.getsize(NDS_PATH) if os.path.exists(NDS_PATH) else 0)
        if rc == 0 and os.path.exists(NDS_PATH):
            ensure_gw()
            sync_sd()
            launch_emulator()


if __name__ == "__main__":
    main()

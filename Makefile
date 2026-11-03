# SPDX-License-Identifier: CC0-1.0
#
# Main Makefile of GameNWatchDS (Game & Watch Emulator DS for Nintendo DS) - BlocksDS.
# with BlocksDS (Wonderful toolchain). Compiles the ARM9 core (emulator + menu)
# and the ARM7 core (standard sound/system services) and packs the NDS ROM
# with ndstool.

include Makefile.common

# User config
# -----------

NAME		:= GameNWatchDS

GAME_TITLE	:= GameNWatchDS
GAME_SUBTITLE	:= G&W collection
GAME_AUTHOR	:= dsaltiveri
GAME_ICON	:= icon.gif

# Set to 1 only when an editor needs compile_commands.json.
COMPDB		?= 0

# Tools
# -----

RM		:= rm -rf

# Verbose flag
# ------------

ifeq ($(VERBOSE),1)
V		:=
else
V		:= @
endif

# Build artifacts
# ---------------

ROM		:= $(NAME).nds

# Targets
# -------

.PHONY: all clean rebuild compdb arm9 arm7

all: $(ROM)

rebuild:
	$(V)+$(MAKE) clean --no-print-directory
	$(V)+$(MAKE) all COMPDB=0 --no-print-directory

compdb:
	$(V)+$(MAKE) clean --no-print-directory
	$(V)+$(MAKE) all COMPDB=1 --no-print-directory

clean:
	@echo "  CLEAN"
	$(V)$(MAKE) -f Makefile.arm9 clean --no-print-directory
	$(V)$(MAKE) -f Makefile.arm7 clean --no-print-directory
	$(V)$(RM) $(ROM) build compile_commands.json

arm9:
	$(V)+$(MAKE) -f Makefile.arm9 COMPDB=$(COMPDB) --no-print-directory

arm7:
	$(V)+$(MAKE) -f Makefile.arm7 COMPDB=$(COMPDB) --no-print-directory

ifeq ($(COMPDB),1)
# Add an additional dependency to the "all" rule
all: compile_commands.json

compile_commands.json: arm9 arm7
	@echo "  MERGE   compile_commands.json"
	$(V)$(WONDERFUL_TOOLCHAIN)/bin/wf-compile-commands-merge $@ \
		build/*/compile_commands.json
endif

$(ROM): arm9 arm7
	@echo "  NDSTOOL $@"
	$(V)$(BLOCKSDS)/tools/ndstool/ndstool -c $@ \
		-7 build/arm7.elf -9 build/arm9.elf \
		-b $(GAME_ICON) "$(GAME_TITLE);$(GAME_SUBTITLE);$(GAME_AUTHOR)"

# Default host validation; emulator and hardware runs remain explicit.
.PHONY: test
test:
	$(PYTHON) tests/run_all_tests.py

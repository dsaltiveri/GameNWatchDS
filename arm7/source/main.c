// SPDX-License-Identifier: Zlib
//
// ARM7 core - FIRE DS (standard: sound, system and input by VBlank).
//
// The game and the audio run on the ARM9 by VBlank. This ARM7 only
// provides the standard libnds services (sound, system and input
// registers) that the ARM9 uses through FIFO.

#include <nds.h>
#include <nds/arm7/audio.h>

static volatile bool exit_loop = false;

static void power_button_callback(void)
{
    exit_loop = true;
}

int main(void)
{
    // Standard ARM7 initialization
    readUserSettings();
    ledBlink(LED_ALWAYS_ON);

    irqInit();
    fifoInit();

    // Standard FIFO handlers (system, sound, input)
    installSystemFIFO();
    installSoundFIFO();

    touchInit();

    // Enable the sound hardware (bias + master volume)
    enableSound();

    // Power button (DSi, no effect on DS)
    setPowerButtonCB(power_button_callback);

    // Input handler sent by VBlank
    irqSet(IRQ_VBLANK, inputGetAndSend);
    irqEnable(IRQ_VBLANK);

    // Main loop
    while (!exit_loop)
    {
        swiWaitForVBlank();
    }

    return 0;
}

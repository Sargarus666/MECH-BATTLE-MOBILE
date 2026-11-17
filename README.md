# MECH BATTLE Mobile

Native Android frontend for Sega Genesis / Mega Drive games.

## Current implementation
- Native Android application (not a web wrapper).
- User selects a ROM using Android's Storage Access Framework.
- ROM is copied into the app-private files directory; no copyrighted game data is bundled.
- LibretroDroid frontend with the PicoDrive core downloaded during CI for arm64-v8a.
- Touch controls for D-pad, A/B/C and Start; hardware gamepad input is handled by LibretroDroid.
- Save state slot and SRAM persistence.

## Build
GitHub Actions downloads the arm64 PicoDrive core and runs `gradle assembleDebug`.
Run the workflow manually from Actions or push a change to `main`.

The APK is published as the workflow artifact `MECH-BATTLE-Mobile-debug`.

## Legal
This repository does not include game ROMs. Use only ROMs you are legally entitled to use.
LibretroDroid is GPL-3.0; see its upstream repository and license for the corresponding source and notices.

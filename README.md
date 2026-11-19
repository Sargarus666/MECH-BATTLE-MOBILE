# MECH BATTLE Mobile

Native Android project for a Sega Genesis / Mega Drive BattleTech port.

## Honest project status

The current Android APK is a **native Android host using LibretroDroid + PicoDrive as a temporary fallback/reference path**. It is not a BattleTech static-recompilation port, and its on-screen controls are not a substitute for game-specific native recompilation.

The required target is a ROM-revision-specific generated-native program: 68000 and sound-driver code translated ahead of execution, linked to a Genesis hardware runtime, then hosted by Android through the NDK. No BattleTech ROM, BIOS, extracted game code, or game assets belong in this repository.

The static-recompiler comparison and current decision are recorded in [docs/recompiler-evaluation.md](docs/recompiler-evaluation.md). The ROM-independent header/vector probe is in tools/genesis_rom_probe.py; it never writes ROM bytes or generated code.

## Current fallback build

- Native Kotlin Android activity; no browser or PWA.
- User selects a ROM with Android's Storage Access Framework.
- LibretroDroid 0.13.2 with PicoDrive downloaded during CI for arm64-v8a.
- Debug APK built by GitHub Actions; artifact retention is 14 days.
- This build is only a temporary compatibility/reference frontend, not evidence that BattleTech works in a static recompiler.
- CI separately builds the pinned Genesis C11 runtime and cross-compiles its Genesis/Z80/audio libraries for Android arm64-v8a (API 23); those libraries are not yet linked into this APK.

## Build

GitHub Actions builds the host and Android C11 runtime libraries, runs Python and Android unit tests, downloads the arm64 PicoDrive core, and runs `testDebugUnitTest assembleDebug`.
The workflow runs on pushes to main and can be started manually from Actions.

The APK is uploaded as the workflow artifact MECH-BATTLE-Mobile-debug.

## Local ROM analysis

Run:

    python3 tools/genesis_rom_probe.py /path/to/your-game.bin
    python3 -m unittest discover -s tools/tests -v

The probe accepts a raw linear Genesis image or a ZIP containing exactly one .bin, .gen, .md, or .rom image. Interleaved .smd files are deliberately rejected until a tested normalizer is added. The probe reports the image hash, header, checksum, reset vector and valid vector-table entry candidates. It does not claim full 68000/Z80 discovery.

Keep the original ROM, all dumps, disassemblies, and generated C in a private local workspace. The repository's .gitignore blocks common ROM and derived-output extensions.

## Legal

Use only ROMs you are legally entitled to use. Do not upload ROMs, BIOS files, proprietary game assets, or ROM-derived code to this repository or its GitHub Actions artifacts. Check every upstream license before incorporating source or binaries.

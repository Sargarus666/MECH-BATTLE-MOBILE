# Static recompiler evaluation — BattleTech (Genesis)

**Review date:** 2026-11-18  
**Target:** the user's exact Sega Genesis / Mega Drive BattleTech: A Game of Armored Combat ROM revision.  
**Compatibility status:** **unknown / not tested**. No ROM archive was available in the current conversation or searchable Library during this review. No BattleTech-specific generated code has been produced.

## Decision

Use **marinocg/segarecomp** as the first candidate for a private, revision-specific feasibility build. Do not treat the game as supported until the exact image passes code discovery, native compilation, deterministic boot, and gameplay comparison. Keep PicoDrive only as a temporary reference runner for differential tests.

Why this is the most realistic starting point:

- Its Genesis target emits portable C11 for both MC68000 and Z80; the published architecture says no interpreter, JIT, or runtime target-opcode decoder.
- It has a separated strict-C11 Genesis runtime and optional SDL3 viewer/launcher targets. The Android direction is therefore to build the runtime/generated program with the NDK and provide a separate Android host, not to port the desktop SDL viewer wholesale.
- The repository's primary license is MPL-2.0; vendored components retain their own notices and licenses. The current Genesis implementation includes VDP, YM2612/PSG, two three-button pads, SRAM/EEPROM persistence, and whole-machine save states.
- The project explicitly reports unsupported behavior instead of silently treating an incomplete build as compatible.

This is a **toolchain choice**, not a BattleTech compatibility claim. The public compatibility ledger names Sonic titles and Streets of Rage, but not BattleTech. Its Genesis limitations include no six-button controller, 60 Hz execution even for PAL-region images, and incomplete compatibility for unlisted games.

**Version caveat:** GitHub's Releases API reports v0.8.0 published 2026-11-08, while the current main README and compatibility ledger still refer to v0.7.0. Before adopting it, pin an exact upstream commit/tag and reconcile the release/source boundary rather than assuming the release and main branch contain identical features.

## Candidate comparison

| Candidate | Current upstream evidence | License / Android portability | Assessment for this project |
|---|---|---|---|
| [marinocg/segarecomp](https://github.com/marinocg/segarecomp) | GitHub latest release is v0.8.0 (2026-11-08). Main README describes static C11 generation for Genesis MC68000 + Z80 and a separate Genesis runtime. Public compatibility ledger does not list BattleTech. | Primary license MPL-2.0; vendored components have separate licenses. The Genesis runtime targets strict C11; SDL3 viewer and launcher are optional CMake targets. No Android build or device validation is documented. | **First candidate.** Most complete generated-native Genesis stack and clearest separation between machine runtime and desktop UI. Android still needs an NDK build, a dedicated native host, and proof that BattleTech's code paths are supported. |
| [mstan/segagenesisrecomp](https://github.com/mstan/segagenesisrecomp) | Latest release v0.1.3 (2026-11-17). Beta 68000-to-C framework; cartridge runner retains a clean-room interpreter fallback for supported dynamic dispatch misses. Cartridge Z80 static recompilation is marked experimental. Public game integrations focus on Sonic and Rocket Knight Adventures, not BattleTech. | PolyForm Noncommercial 1.0.0 for the framework/recompiler. README lists Windows, macOS and Linux runner support; no Android target is documented. | Technically substantial, but the non-commercial license is a distribution constraint and the cartridge fallback does not meet the strict generated-native target as cleanly as segarecomp. Keep as a comparison/reference, not the selected base. |
| [sp00nznet/genrecomp](https://github.com/sp00nznet/genrecomp) | Alpha, unversioned. README reports only Pigskin Footbrawl and General Chaos in-game; audio is not verified by ear and there is no conformance harness. The analyzer uses Capstone and title-specific seeds/dispatch tables. | The toolkit is MIT, but its Genesis Plus GX hardware backend has additional non-commercial redistribution restrictions. SDL2 is a required platform layer; no Android target is documented. | Useful research prototype and reference for dispatch-table discovery. Not the production base: small compatibility sample, unverified audio, approximate timing, instant DMA completion, and mid-frame raster effects out of scope. |

### Upstream evidence and source areas reviewed

- segarecomp: README.md, LICENSE, CHANGELOG.md, platforms/genesis/README.md, platforms/genesis/runtime/CMakeLists.txt, platforms/genesis/runtime/runtime.h, docs/architecture/pipeline.md, docs/product/compatibility-ledger.md, and docs/product/compatibility-ledger.json.
- Genesis Recomp: README.md, LICENSE.md, LICENSE-recompiler, docs/Z80_STATIC_RECOMP.md, docs/DISASSEMBLIES.md, and the runner/platform support section.
- genrecomp: README.md, LICENSE, LICENSES/Genesis-Plus-GX.txt, docs/recompiler.md, docs/recomp-runtime.md, CMakeLists.txt, and include/genrecomp/platform.h.

## ROM-specific unknowns that must be measured

The current evidence is insufficient to choose a per-game integration configuration. Once the exact image is available in a private workspace, the first pass must record:

1. SHA-256, byte size, raw/interleaved format, header signature, product/serial string, declared ROM range, region bytes, and checksum result.
2. Initial 68000 SP/PC and all vector-table targets that map to even ROM addresses.
3. Reachable 68000 instructions, indirect jumps/calls, computed dispatch tables, overlays, code copied to RAM, and self-modifying regions. A vector table is only a set of starting candidates, not complete code discovery.
4. Sound-driver upload sources and all Z80 RAM/code variants. The Genesis header does not identify the Z80 driver; it must be found through 68000 writes/copy loops or runtime evidence.
5. VDP register usage, DMA modes, H/V interrupt timing, raster effects, work-RAM mapping, controller I/O, and any cartridge-specific banking or backup-memory behavior.
6. Save behavior: SRAM/EEPROM address ranges, enable protocol, write timing, and state consistency.
7. Exact controller semantics in the game's manual or a verified in-game control screen. Do not assume generic A/B/C assignments.

For every unsupported opcode or dispatch miss, retain the ROM address and the exact diagnostic from the recompiler. Do not invent a seed or hardware mapping to make a build proceed. A missing generated target, dynamic code, bank switch, or unmodeled device access is a blocker until evidence explains it.

## Android integration boundary

The intended static path is:

    user-owned ROM (private local file)
      -> host-side recompiler / discovery
      -> generated C11 for this exact ROM hash (private build output)
      -> Android NDK compile + Genesis C11 runtime
      -> JNI lifecycle/frame/audio/input bridge
      -> native Android UI and video/audio surfaces

The desktop SDL3 viewer is not the Android UI. The Android host must own pause/resume, audio focus, SAF URI import, a dedicated native execution thread with a sufficiently large stack, 4:3 presentation, audio output, controller state, save paths, and app lifecycle. The generated program and all ROM-derived files must remain outside Git and outside GitHub Actions artifacts.

There is a build-time constraint: static generated code is tied to the exact ROM image. A generic APK that accepts an arbitrary ROM after installation cannot contain that ROM's generated program unless it recompiles locally at runtime or the program is built for a specific image before packaging. No such on-device compiler path is implemented here. The immediate next acceptance gate is therefore a private ROM-specific host build, not a claim that the current generic APK is already a native BattleTech port.

## Current repository state

The current Android app is still the LibretroDroid/PicoDrive fallback. It selects and copies a user ROM, but its touch overlay is not the final control implementation and the APK is arm64-v8a only. The current CI build proves that this fallback APK can be compiled and packaged; it does not prove BattleTech compatibility, static recompilation, game audio fidelity, save correctness, or real-device behavior.

## References

- [segarecomp v0.8.0 release](https://github.com/marinocg/segarecomp/releases/tag/v0.8.0)
- [segarecomp compatibility ledger](https://github.com/marinocg/segarecomp/blob/main/docs/product/compatibility-ledger.md)
- [Genesis Recomp v0.1.3 release](https://github.com/mstan/segagenesisrecomp/releases/tag/v0.1.3)
- [genrecomp README](https://github.com/sp00nznet/genrecomp/blob/master/README.md)

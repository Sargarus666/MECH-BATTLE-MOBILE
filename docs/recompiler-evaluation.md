# Static recompiler evaluation — BattleTech (Genesis)

**Review date:** 2026-11-21  
**Target:** the user's exact Sega Genesis / Mega Drive BattleTech: A Game of Armored Combat ROM revision.  
**Compatibility status:** **unknown / not tested**. A private ROM analysis has now gone beyond header/vector inspection and produced a 68000 reachability report plus generated C, but the generated program has not been compiled, linked to the Genesis runtime, or run. No BattleTech gameplay compatibility is claimed. ROM bytes, hashes, disassembly, and assets remain private and are not committed or uploaded to CI.

## Decision

Use **marinocg/segarecomp** as the first candidate for a private, revision-specific feasibility build. Do not treat the game as supported until the exact image passes code discovery, native compilation, deterministic boot, and gameplay comparison. Keep PicoDrive only as a temporary reference runner for differential tests.

Why this is the most realistic starting point:

- Its Genesis target emits portable C11 for both MC68000 and Z80; the published architecture says no interpreter, JIT, or runtime target-opcode decoder.
- It has a separated strict-C11 Genesis runtime and optional SDL3 viewer/launcher targets. The Android direction is therefore to build the runtime/generated program with the NDK and provide a separate Android host, not to port the desktop SDL viewer wholesale.
- The repository's primary license is MPL-2.0; vendored components retain their own notices and licenses. The current Genesis implementation includes VDP, YM2612/PSG, two three-button pads, SRAM/EEPROM persistence, and whole-machine save states.
- The project explicitly reports unsupported behavior instead of silently treating an incomplete build as compatible.

This is a **toolchain choice**, not a BattleTech compatibility claim. The public compatibility ledger names Sonic titles and Streets of Rage, but not BattleTech. Its Genesis limitations include no six-button controller, 60 Hz execution even for PAL-region images, and incomplete compatibility for unlisted games.

**Version caveat:** this repository pins segarecomp commit 8d419ab (2026-11-17); upstream main is d469ce4 (2026-11-20), two commits ahead with session-recording/replay and launcher-UX changes. The pin was not bumped in this run. GitHub Releases reports v0.8.0 (2026-11-08), while the current main README/ledger still refer to v0.7.0. Do not assume release/source feature parity.

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

## BattleTech input evidence

The available Genesis control guide documents the standard three-button mapping: D-pad for movement/aiming, A/B/C for weapon groups A/B/C, and Start for the pause menu. Holding A charges some A-group weapons; holding B enables rapid fire for B-group weapons. In the two-player mode, Player 1 is the gunner (D-pad aiming plus A/B/C) and Player 2 pilots the legs and movement. The pause menu also uses A/B/C to switch its three pages. See the [GameFAQs Genesis control guide](https://gamefaqs.gamespot.com/genesis/586052-battletech/faqs/61254) and the independent [Genesis controls listing](https://1upheart.com/sega-genesis/battletech-a-game-of-armored-combat/).

This is a game-control mapping, not yet a verified hardware-register mapping for the supplied image. The touch design should preserve independent pointer ownership so the D-pad can remain held while any weapon button is pressed; actual I/O bit assignments and menu-state edge cases still need ROM/code validation. A scanned publisher manual has not yet been located.

## Private ROM analysis

The user's Library contained a ZIP with exactly one linear .gen image. It was extracted only in the private working directory for analysis; no archive or ROM member was copied into the repository or CI.

- Image size: 2 MiB; the Genesis header was recognized and the reset vectors were structurally valid.
- Region field: U.
- Header checksum: stored 0x8103; recomputed 0x0283 — mismatch. The image was not modified to “fix” the checksum. The archive is labelled as a translated image, but that alone is not proof of why the checksum differs.
- Reset SP resolves through the 24-bit bus alias into work RAM; reset PC is a valid even ROM target.
- segarecomp inspect recognized Genesis; analyze accepted the reset image with an initial identity, non-mirrored raw cartridge mapping covering the 2 MiB image. This does not prove that no later bank switching or RAM overlay occurs.

The private SHA-256 is available only in the local audit output and is intentionally not recorded in Git. The reusable tool is tools/segarecomp_rom_audit.py. It reads a ROM or one-member ZIP in memory, places a temporary copy in a temporary directory for the CLI, and emits only aggregate discovery counts and image metadata. Full reachability reports are deleted with the temporary directory. Optional generated C must be directed outside the repository.

Example (keep both outputs outside the checkout):

~~~sh
python3 tools/segarecomp_rom_audit.py /private/path/battletech.zip \
  --cli /private/path/segarecomp \
  --report /private/path/battletech-audit.json \
  --emit-c /private/path/battletech-generated.c
~~~

The audit tests use a fake CLI and a synthetic fixture; CI never receives the user's ROM.

## 68000 discovery results

The specialized genesis-rom-startup check returned startup_graph_mismatch. This is a startup-pattern mismatch, not evidence of an unsupported 68000 opcode.

The broader genesis-general-startup analysis returned partial after 138 completed blocks and reported 17 frontiers:

- one unmapped byte-write frontier at 68000 PC `0x00000314` to address `0x00208000`, inside the standard cartridge decode window but outside this image's 2 MiB declared ROM range;
- sixteen discovery-prefix-budget frontiers.

This is a cartridge-window access, **not a VDP access**. Sega's Technical Overview places cartridge ROM at `$000000–$3FFFFF` and the VDP ports at `$C00000` (pp. 7 and 18; [technical overview PDF](https://segaretro.org/images/1/18/GenesisTechnicalOverview.pdf)). The supplied header declares ROM range `$000000–$1FFFFF`; its optional external-memory descriptor is blank (see [Genesis ROM header reference](https://www.plutiedev.com/rom-header)). Those facts do not establish whether `$208000` aliases the 2 MiB image, returns open-bus data, or is decoded by cartridge-specific hardware. The current non-mirrored mapping claim ends at `$00200000`, so this remains an unresolved cartridge mapping/hardware frontier—not evidence of an unsupported CPU opcode.

A separate strict reachability pass with PC-index recovery found:

| Measure | Result |
|---|---:|
| Discovered instruction starts | 19,140 |
| Call continuations | 1,251 |
| Indirect JSR (An) sites | 17 |
| Indexed PC-relative JMP sites | 1 |
| Out-of-ROM target candidates | 2 |
| Rejected decode targets | 0 |
| Odd decode targets | 0 |

The single indexed PC-relative jump remains unresolved: PC-index recovery reports index_unknown, originating from an untracked load/source, and recovers zero table targets. The separate PC-relative offset-table proposal command returned no proposals. The 17 indirect JSR (An) sites still need their concrete target sets and dispatch-table ownership established. The two out-of-ROM target candidates have not been assigned a meaning; they must not be guessed into a mapping.

A separate per-word-position decode-token report was cross-checked against the 19,140 instruction starts in this reachability set: 19,134 were classified as ordinary decodes, 6 as architectural exception forms, and 0 as rejected/undecodable/truncated. The ordinary family counts were move 9,157; arithmetic 3,852; logic/bit 488; shift 705; control 4,382; other 550. Its control tokens independently classified 17 dynamic calls and 1 dynamic jump, matching the 17 `JSR (An)` sites and the single PC-indexed `JMP` in the reachability report. The token report is classification evidence only: it does not resolve those targets, prove code/data ownership, or validate generated-code lowering/runtime behavior.

No unsupported 68000 opcode has been positively identified in the discovered instruction starts. This is not proof of full compatibility: indirect dispatch, the cartridge-window access, the remaining discovery frontiers, and generated-code execution are still unresolved.

An optional PEA-continuation heuristic increased overlapping starts, rejected targets, and odd targets without resolving the indexed site, so it is not used for the baseline report.

## Z80/audio discovery results

The segarecomp Z80 static report is partial:

- 2 candidates, 1 reconstructed image, 1 copy loop;
- 3,036 analysis steps, 1,210 nodes, 65 contexts, 7 horizon paths;
- 1 length_unknown refusal and 1 state_bound refusal;
- 0 decoder calls and 0 staged decodes in this report.

This is not enough to claim that BattleTech's sound driver has been statically reconstructed. The upload/copy path, complete Z80 RAM image(s), live variants, YM2612/PSG writes, BUSREQ/reset timing, and audio parity still require proof.

## Generated-native output

emit-general-startup-bridge-c successfully emitted 32,460,761 bytes of C into the private working directory. This is a code-generation milestone, not a complete game build:

- the generated C has not been compiled against the Genesis runtime;
- no executable has been linked;
- no headless frame, framebuffer, sound, save, or input replay has been compared with PicoDrive;
- no BattleTech-specific Android native library or APK has been produced.

The generated C and all intermediate reports remain outside Git.

## Current CI and APK boundary

The latest repository workflow run checked here is run #32, commit 12acbabb8c96bd99ed5c64eb1c31a5002e75b764, completed successfully on 2026-11-20.

Successful steps include:

- pinned segarecomp source verification and portable CLI build/smoke tests;
- host build of Genesis C11 runtime libraries;
- Android NDK cross-compilation of Genesis, Z80, and audio runtime libraries for arm64-v8a and x86_64 at API 23;
- ROM-independent Python tests;
- Gradle testDebugUnitTest and assembleDebug;
- ZIP, zipalign, apksigner, package ID, SDK and ABI checks;
- install and launch on an Android 15 / API 35 x86_64 emulator, with no fatal exception or native-link error in the checked log.

The uploaded debug APK is still the temporary Libretro/PicoDrive fallback, not the native BattleTech port. Inspecting the APK confirms it contains liblibretrodroid.so and libpicodrive_libretro_android.so, and does not contain the segarecomp runtime. It packages com.sargarus.mechbattle, minSdk 23, targetSdk 35, ABIs arm64-v8a and x86_64. Emulator launch success validates only the fallback app shell, not BattleTech gameplay, static recompilation, audio fidelity, or save behavior.

The workflow uploads artifacts with 14-day retention. It does not upload ROMs, generated code, or secrets. GitHub-hosted Actions remain subject to the account's actual included minutes and storage quotas.


## Android integration boundary

The intended static path is:

    user-owned ROM (private local file)
      -> host-side recompiler / discovery
      -> generated C11 for this exact ROM hash (private build output)
      -> Android NDK compile + Genesis C11 runtime
      -> JNI lifecycle/frame/audio/input bridge
      -> native Android UI and video/audio surfaces

The desktop SDL3 viewer is not the Android UI. The Android host must own pause/resume, audio focus, SAF URI import, a dedicated native execution thread with a dedicated native worker thread with an explicitly provisioned 8 MiB stack (the upstream runtime documents this POSIX requirement), 4:3 presentation, audio output, controller state, save paths, and app lifecycle. The generated program and all ROM-derived files must remain outside Git and outside GitHub Actions artifacts.

There is a build-time constraint: static generated code is tied to the exact ROM image. A generic APK that accepts an arbitrary ROM after installation cannot contain that ROM's generated program unless it recompiles locally at runtime or the program is built for a specific image before packaging. No such on-device compiler path is implemented here. The immediate next acceptance gate is therefore a private ROM-specific host build, not a claim that the current generic APK is already a native BattleTech port.

## Current repository state

The Android app remains a native Kotlin UI around the temporary LibretroDroid/PicoDrive fallback. It has pointer-owned multi-touch input, but it is not a static BattleTech port. The latest debug APK packages arm64-v8a and x86_64, minSdk 23, targetSdk 35. The CI emulator launch proves only that the fallback shell starts; it does not prove game compatibility or native recompiled execution.

## References

- [segarecomp v0.8.0 release](https://github.com/marinocg/segarecomp/releases/tag/v0.8.0)
- [segarecomp compatibility ledger](https://github.com/marinocg/segarecomp/blob/main/docs/product/compatibility-ledger.md)
- [Genesis Recomp v0.1.3 release](https://github.com/mstan/segagenesisrecomp/releases/tag/v0.1.3)
- [genrecomp README](https://github.com/sp00nznet/genrecomp/blob/master/README.md)

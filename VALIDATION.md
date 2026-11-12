# Quality-of-life candidate validation — October 8, 2026

## Checks performed

- Development Python suite: 100 tests passed, including an authentic local terrain preparation/travel coverage test using owned assets.
- Source-only candidate Python suite: 100 tests completed, 99 passed and 1 authentic game-asset test skipped as intended. No game resources are in the candidate.
- Clean offline Fabric build: successful, all 44 Java tests passed. Covers triangle movement/collision, unknown region boundaries, eviction/reload, tracking guards, and native pick origin validation.
- C++ viewport and presentation assertions: both compiled and passed. These exercise 1080p, wide/tall windows, invalid/empty dimensions, stabilization and loading/frontier presentation.
- Renderer addon compiled successfully against ReShade 6.8 headers with Zig 0.15.2. Installed via hash synchronization while isolated Cemu was stopped.
- Native source preflight and regeneration passed in the separate candidate directory.
- Setup doctor reported all 12 dependencies ready on the development PC; it starts no game processes and does not inspect accounts or saves.

## Live isolated checks

Physical mouse capture remained disabled. Existing BOTW save and Minecraft world were used; no house blocks were edited.

The direct-camera test measured a 5.9990439075 degree turn for an 80-pixel scripted stroke at mouse_scale 0.5, with 0 degree late drift. This verifies a native camera endpoint; it is not a subjective physical-mouse feel test.

The renderer's display request round-trip measured windowed 1278x762 → fullscreen 2560x1440 → windowed 1278x762, twice, with every request consumed. It exercises the same toggle implementation used by startup and F11; it does not prove a physical F11 press on every layout. No screenshot-based visual acceptance was claimed.

The bounded host exited after testing and reported input capture disabled. Full BOTW object collision, prolonged travel, native support during arbitrary jumps/buildings, all visual effects, and Survival remain unfinished. Earlier travel failures are not superseded by the checks above.

## Source candidate

Only source, native assembly/definitions, tests, build metadata, example configuration and licenses were copied by an explicit allowlist. No saves, game assets, keys, accounts, personal local configuration, gameplay screenshots, binaries or local runtime logs are included. The only jar is Gradle's standard build wrapper. Source path/credential-pattern scan found no matching private Windows user paths or token patterns; this is a scoped source scan, not an account audit.

The local Git repository has no remote and has not been published. CI definitions are included but have not yet run on GitHub. A new machine still needs its own compatible runtimes and authentic terrain setup. The declared Loom snapshot can resolve differently outside the tested cache.

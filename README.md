# HyruleCraft

Experimental Creative Minecraft gameplay composited into **Breath of the Wild on Cemu**. Based on [SkyCraft](https://github.com/chasmlol/SkyCraft), with its MIT license and namespaces retained. Survival is future work.

Minecraft supplies real blocks, inventory, hand, skin, Creative flight and F5 camera modes. The bridge streams authenticated BOTW heightfields, synchronizes bounded Link corrections and renders Minecraft meshes/UI through an OpenGL ReShade addon. Scene lighting/fog is approximate.

**Development status:** native rocks/buildings, bridges, water and caves are not covered by the heightfield exporter. Corrections can clip through native objects. Long travel, continuous moving/jumping support and every physical input layout are not certified. This is an experimental integration, not native Minecraft or a finished gameplay release.

## Setup

Windows x64, Python 3.12 x64, Java 25, Cemu 2.6 with OpenGL, BOTW Wii U US update 208, Minecraft Java 26.3, Fabric loader 0.19.5, Fabric API 0.161.0+26.3, a separate Prism instance named `HyruleCraft-dev`, and ReShade 6.8 addon support are the tested environment. Use your own games and pre-extracted authentic terrain data. No games, keys, account files, saves, runtime textures or emulator binaries are included.

1. Build the source using [BUILDING.md](BUILDING.md).
2. Prepare a dedicated Cemu directory and separate MLC save directory. Install the compatible ReShade addon runtime yourself; enable the native HyruleBlocks and HyruleCraft1080p graphics packs. Keep original installations separate.
3. Prepare a separate Prism instance with the matching Minecraft/Fabric versions. Install the built Fabric jar and compatible Fabric API. Set JVM arguments `--enable-native-access=ALL-UNNAMED -Dskycraft.startHidden=true -Dskycraft.quitWithSkyrim=true`. The mod uses a Creative mirror save; back up your world before development updates.
4. Copy `hyrulecraft.example.json` to **hyrulecraft.local.json**, then set your local Cemu, title, terrain and Prism paths. Terrain data must include `MainField.tscb` and the relevant `MainField/*.hght` files or `.hght.sstera` packs. The public source does not include the private extraction environment used on the development PC.
5. Run `python launch.py --doctor`. It lists missing dependencies without starting games or inspecting accounts/saves. Then run `Play-HyruleCraft.cmd`.

The launcher checks artifact hashes and installs newer addon/shader/native patch/Fabric builds only while each owner is stopped. Close the isolated game normally before updating. Loading a save remains explicit: **Continue → your existing save → Start**; Enter confirms, arrows choose, Backspace goes back. Input engages once the world is ready.

## Controls and preferences

| Control | Action |
| --- | --- |
| WASD / Space | Move / jump |
| Shift / Ctrl | Sneak or descend / sprint |
| Double-tap Space | Toggle Creative flight |
| Mouse / left click / right click | Look / mine / use or place |
| Wheel / 1–9 | Hotbar |
| E / T / Escape | Inventory / chat / pause or close menu |
| F5 | First person → third person behind → third person front |
| F7 | Release or reacquire Minecraft input |
| F8 | Explicit recovery to a previously verified nearby calibration point, when available |
| F11 | Toggle TV borderless fullscreen |
| Alt-Tab | Release capture and switch applications |

Pause/inventory expose the cursor. Capture and cursor hiding are limited to focused gameplay with fresh endpoints; desktop chords release keys and mouse recentering. Fullscreen uses one borderless state for both startup and F11, with prior window placement restored. Internal BOTW rendering remains 1080p; monitor presentation can be larger.

`mouse_scale` is a multiplier on Minecraft's sensitivity, default **0.5**. Set it to `0.25` for slower camera motion, or override one launch with `python launch.py --mouse-scale 0.25`. `invert_y` and `fullscreen` are JSON booleans. `--windowed` overrides fullscreen for one launch. Preferences apply at startup. `python status.py` prints read-only runtime health and rejects stale status as live evidence.

## Testing and evidence

Run `python run_tests.py`. Tests cover input/focus cleanup, mouse endpoints, calibration validation, bounded movement/recovery, terrain streaming/cache/backpressure, launcher update ownership, config errors, diagnostics, normal shutdown and stale status. Authentic terrain tests skip when local game resources are absent; synthetic/pure checks remain available. Java tests run with the Fabric build, and C++ presentation/viewport checks are described in BUILDING.md.

Live camera tests use `python launch.py --no-input --windowed --mouse-stop-probe --seconds 90`; physical mouse capture stays disabled. Short scripted travel tests exist but do not prove arbitrary travel or full native collision. See [VALIDATION.md](VALIDATION.md) for the candidate's actual checks and limitations.

## GitHub preparation

This source package contains an initialized local Git repository and CI definitions. It has no remote and has not been published. Review the files, create an empty repository in your GitHub account, then commit and push using your own Git identity. Keep `hyrulecraft.local.json`, game assets, saves, credentials and builds out of Git. Runtime shaders use Minecraft's live atlas rather than redistributing it.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [LICENSE](LICENSE) and the preserved third-party license files.

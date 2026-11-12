# Source and runtime credits

SkyCraft by chasmlol: https://github.com/chasmlol/SkyCraft. The adapted Fabric source and protocol are MIT licensed; the complete original license is preserved in `fabric/LICENSE`.

ReShade by Patrick Mours: https://github.com/crosire/reshade/tree/v6.8.0. The renderer uses its addon SDK. The applicable BSD 3-Clause license is included in `renderer/LICENSE-ReShade.txt`. The official runtime is a separate development dependency, not an original HyruleCraft implementation.

BOTW addresses, virtual-function layout and transform semantics were researched from WiiXLaunch-BotW: https://github.com/TKVSC-Team/WiiXLaunch-BotW. Only reverse-engineering facts were used for the new player-thread assembly; WiiXLaunch C++ implementation was not copied into this addon. The existing HyruleBlocks first-person patch uses BetterVR research credited in `native/THIRD_PARTY_NOTICES.md`.

Minecraft and BOTW assets are provided by the user's installed games. The addon receives Minecraft's runtime texture atlas; it does not ship that atlas or BOTW assets.

The Gradle wrapper and build tooling originate from Gradle and are Apache-2.0 licensed: https://github.com/gradle/gradle/blob/master/LICENSE. The 1080p rule attribution is preserved inline in graphics/HyruleCraft1080p/rules.txt; the upstream graphics pack is CC0-1.0; its license is preserved in graphics/LICENSE-Cemu-Graphic-Packs.md. The Gradle license is preserved in fabric/gradle/LICENSE-Gradle.txt.

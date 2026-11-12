# Building HyruleCraft

This is a Windows development project. Dependencies are user-provided; the source bundle does not install or download games/runtimes.

## Fabric

Set `JAVA_HOME` to Java 25 and use the Gradle wrapper:

```powershell
.\fabric\gradlew.bat -p fabric --no-daemon build
```

Initial builds require access to the configured official dependency repositories. `--offline` works only with a populated Gradle cache. The tested local cache resolves Loom 1.18.2 from the declared 1.18-SNAPSHOT; a fresh machine's snapshot resolution may differ. Artifact: `fabric/build/libs/hyrulecraft-0.1.0-botw-dev.jar`. The build runs the Java collision/streaming/pick-origin/tracking tests. The wrapper is Gradle's third-party Apache-2.0 tooling.

## Native patch

```powershell
python native/build.py
```

The bundled native assembly and generated patch are source, not game assets. On the historical development layout, the companion is `../HyruleBlocks`; `native_directory` handles both layouts.

## OpenGL renderer

Use Zig 0.15.2 and ReShade 6.8's official addon headers. From the source root:

```powershell
New-Item -ItemType Directory -Force dist
zig c++ renderer/renderer.cpp -shared -std=c++20 -O2 -Wno-unknown-attributes -I<Path-to-ReShade-SDK>/include -lopengl32 -lgdi32 -luser32 -o dist/HyruleCraft.addon64
```

No aggregate-return calls cross the ReShade SDK ABI boundary. Vulkan is unsupported. Keep the shader `renderer/HyruleCraft.fx` alongside the installed addon. Change built artifacts only after their game owner has stopped; launcher hash sync refuses running replacements.

## Tests

```powershell
python run_tests.py
zig c++ tests/test_viewport.cpp -std=c++20 -o viewport-test.exe
.\viewport-test.exe
zig c++ tests/test_presentation.cpp -std=c++20 -o presentation-test.exe
.\presentation-test.exe
```

The C++ header checks are also portable to g++. CI runs the Python suite on Windows and those header checks on Linux. CI does not run live BOTW, package game resources, or certify native object collision.

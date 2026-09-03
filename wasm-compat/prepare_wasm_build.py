from pathlib import Path

# The selected SFML fork is already Emscripten-aware. The old compatibility
# script was written for vanilla SFML 2.5.1 and would overwrite that support.
# Keep this step as a deterministic verification-only pass because the
# workflow still calls it before configuring SFML.

sfml_config = Path("sfml-src/include/SFML/Config.hpp")
sfml_cmake = Path("sfml-src/cmake/Config.cmake")

if not sfml_config.is_file():
    raise RuntimeError("SFML Config.hpp is missing")
if not sfml_cmake.is_file():
    raise RuntimeError("SFML cmake/Config.cmake is missing")

config_text = sfml_config.read_text(encoding="utf-8")
cmake_text = sfml_cmake.read_text(encoding="utf-8")

if "__EMSCRIPTEN__" not in config_text:
    raise RuntimeError("Selected SFML fork does not contain Emscripten platform support")
if "EMSCRIPTEN" not in cmake_text:
    raise RuntimeError("Selected SFML fork does not contain Emscripten CMake support")

print("Verified Emscripten-aware SFML fork; legacy SFML 2.5.1 patching skipped")

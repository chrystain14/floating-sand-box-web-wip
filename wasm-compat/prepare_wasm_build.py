from pathlib import Path
import os
import runpy

# SFML 2.5.1 does not reliably receive the Emscripten platform macro from its
# own CMake detection under Emscripten 3.1.12. Force the canonical compiler
# macro into both C and C++ compilation so Config.hpp and platform-specific
# sources consistently take the WebAssembly path.
for var in ("CFLAGS", "CXXFLAGS"):
    current = os.environ.get(var, "")
    if "-D__EMSCRIPTEN__" not in current:
        os.environ[var] = (current + " -D__EMSCRIPTEN__").strip()

# Keep the main entry point wired to the complete compatibility pass. That
# pass restores the SFML 2.5.1 WebAssembly patches and applies the Emscripten
# platform fix before the SFML build begins.
runpy.run_path(str(Path(__file__).with_name("prepare_wasm_build_base.py")), run_name="__main__")

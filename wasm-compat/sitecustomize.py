"""Extra safety net for the SFML 2.5.1 Emscripten build.

Python loads sitecustomize automatically when this directory is on sys.path.
The workflow invokes prepare_wasm_build.py from wasm-compat, so this hook runs
immediately before that compatibility script and force-normalizes SFML's
platform detection for the pinned Emscripten toolchain.
"""
from pathlib import Path

config_h = Path("sfml-src/include/SFML/Config.hpp")
if config_h.exists():
    text = config_h.read_text(encoding="utf-8")
    marker = "#elif defined(__unix__)"
    if marker in text and "#define SFML_SYSTEM_EMSCRIPTEN" not in text:
        replacement = (
            "#elif defined(EMSCRIPTEN) || defined(__EMSCRIPTEN__) || defined(__wasm__)\n\n"
            "    // Emscripten / WebAssembly\n"
            "    #define SFML_SYSTEM_EMSCRIPTEN\n\n"
            "#elif defined(__unix__)"
        )
        config_h.write_text(text.replace(marker, replacement, 1), encoding="utf-8")
        print("sitecustomize: forced SFML Emscripten platform branch")
    elif "#define SFML_SYSTEM_EMSCRIPTEN" in text:
        print("sitecustomize: SFML Emscripten platform branch already present")

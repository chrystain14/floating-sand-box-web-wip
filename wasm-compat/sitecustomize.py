"""Extra safety net for the SFML 2.5.1 Emscripten build.

Python loads sitecustomize automatically when this directory is on sys.path.
The workflow invokes prepare_wasm_build.py from wasm-compat, so this hook runs
immediately before that compatibility script and force-normalizes SFML's
platform detection for the pinned Emscripten toolchain.
"""
from pathlib import Path
import os

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

# SFML 2.5.1's ALCheck headers include legacy flat OpenAL names (<al.h>,
# <alc.h>), while Emscripten exposes the modern <AL/al.h> and <AL/alc.h>.
# Add local forwarding headers so the old SFML source resolves cleanly.
sysroot = Path(os.environ.get("EM_SYSROOT", ""))
if sysroot:
    for source_name, target in (
        ("al.h", Path("sfml-src/include/al.h")),
        ("alc.h", Path("sfml-src/include/alc.h")),
    ):
        source = sysroot / "include" / "AL" / source_name
        if source.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source.resolve())
            print(f"sitecustomize: added legacy OpenAL forwarding header {target}")

from pathlib import Path
import os
import runpy
import tempfile
import urllib.request

# Reuse the known-good WASM compatibility preparation from the last stable
# staging point, then apply the additional fixes needed by the current build.
url = "https://raw.githubusercontent.com/chrystain14/floating-sand-box-web-wip/5dad57eb1479d91af16e6e85cd444f144671a171/wasm-compat/prepare_wasm_build.py"
with urllib.request.urlopen(url, timeout=30) as response:
    original = response.read().decode("utf-8")

with tempfile.TemporaryDirectory(prefix="floating-sandbox-wasm-") as tmp:
    helper = Path(tmp) / "prepare_original.py"
    helper.write_text(original, encoding="utf-8")
    runpy.run_path(str(helper), run_name="__main__")

SFML_ROOT = Path("sfml-src")

# SFML 2.5.1's public Config.hpp does not recognize Emscripten and falls into
# its unsupported-UNIX #error. Apply the fix after all helper preparation so it
# cannot be overwritten by another compatibility pass.
sfml_config = SFML_ROOT / "include/SFML/Config.hpp"
text = sfml_config.read_text(encoding="utf-8")
old = '''    #else

        // Unsupported UNIX system
        #error This UNIX operating system is not supported by SFML library

    #endif'''
new = '''    #else

    #if defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)

        // Emscripten
        #define SFML_SYSTEM_EMSCRIPTEN

    #else

        // Unsupported UNIX system
        #error This UNIX operating system is not supported by SFML library

    #endif

    #endif'''
if "#define SFML_SYSTEM_EMSCRIPTEN" not in text:
    if old not in text:
        raise RuntimeError("Could not locate SFML unsupported UNIX branch")
    sfml_config.write_text(text.replace(old, new, 1), encoding="utf-8")

# SFML 2.5.1 has no misc install directory case for Emscripten.
sfml_cmake = SFML_ROOT / "CMakeLists.txt"
text = sfml_cmake.read_text(encoding="utf-8")
old = '''elseif(SFML_OS_ANDROID)
    set(DEFAULT_INSTALL_MISC_DIR ${CMAKE_ANDROID_NDK}/sources/third_party/sfml)
endif()'''
new = '''elseif(SFML_OS_ANDROID)
    set(DEFAULT_INSTALL_MISC_DIR ${CMAKE_ANDROID_NDK}/sources/third_party/sfml)
elseif(SFML_OS_EMSCRIPTEN)
    set(DEFAULT_INSTALL_MISC_DIR .)
endif()'''
if "elseif(SFML_OS_EMSCRIPTEN)" not in text:
    if old not in text:
        raise RuntimeError("Could not locate SFML Android install-directory branch")
    sfml_cmake.write_text(text.replace(old, new, 1), encoding="utf-8")

# Emscripten's OpenAL headers are namespaced under AL/.
audio_root = SFML_ROOT / "src/SFML/Audio"
include_replacements = {
    "#include <al.h>": "#include <AL/al.h>",
    "#include <alc.h>": "#include <AL/alc.h>",
    "#include <alext.h>": "#include <AL/alext.h>",
}
for path in audio_root.rglob("*"):
    if not path.is_file() or path.suffix not in {".h", ".hpp", ".cpp", ".inl"}:
        continue
    source = path.read_text(encoding="utf-8")
    updated = source
    for old_include, new_include in include_replacements.items():
        updated = updated.replace(old_include, new_include)
    if updated != source:
        path.write_text(updated, encoding="utf-8")

# Hard validation: the two critical Emscripten fixes must be present in the
# source that will actually be compiled.
patched = sfml_config.read_text(encoding="utf-8")
if "#define SFML_SYSTEM_EMSCRIPTEN" not in patched:
    raise RuntimeError("SFML Config.hpp Emscripten fix is missing")

print("WASM compatibility preparation completed successfully")

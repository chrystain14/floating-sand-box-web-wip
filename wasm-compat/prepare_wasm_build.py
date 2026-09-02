from pathlib import Path
import runpy
import tempfile
import urllib.request

# SFML 2.5.1 can reject Emscripten in its public Config.hpp. Patch the exact
# unsupported-UNIX fallback so Emscripten is recognized deterministically.
sfml_config = Path("sfml-src/include/SFML/Config.hpp")
text = sfml_config.read_text(encoding="utf-8")
old = """    #else\n\n        // Unsupported UNIX system\n        #error This UNIX operating system is not supported by SFML library\n\n    #endif"""
new = """    #else\n\n    #if defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)\n\n        // Emscripten\n        #define SFML_SYSTEM_EMSCRIPTEN\n\n    #else\n\n        // Unsupported UNIX system\n        #error This UNIX operating system is not supported by SFML library\n\n    #endif\n\n    #endif"""
if "#define SFML_SYSTEM_EMSCRIPTEN" not in text:
    if old not in text:
        raise RuntimeError("Could not locate SFML unsupported UNIX branch")
    sfml_config.write_text(text.replace(old, new, 1), encoding="utf-8")

patched = sfml_config.read_text(encoding="utf-8")
if "#define SFML_SYSTEM_EMSCRIPTEN" not in patched:
    raise RuntimeError("SFML Config.hpp was not patched for Emscripten")

# Run the established compatibility preparation implementation pinned to the
# staging base commit so upstream changes cannot silently alter the build.
url = "https://raw.githubusercontent.com/chrystain14/floating-sand-box-web-wip/da3d0e50138c1b2854cecf940167e067685ac89e/wasm-compat/prepare_wasm_build.py"
with urllib.request.urlopen(url, timeout=30) as response:
    original = response.read().decode("utf-8")

with tempfile.TemporaryDirectory(prefix="floating-sandbox-wasm-") as tmp:
    helper = Path(tmp) / "prepare_original.py"
    helper.write_text(original, encoding="utf-8")
    runpy.run_path(str(helper), run_name="__main__")

# Ensure the helper did not overwrite our header fix.
patched = sfml_config.read_text(encoding="utf-8")
if "#define SFML_SYSTEM_EMSCRIPTEN" not in patched:
    raise RuntimeError("SFML Config.hpp Emscripten marker disappeared during preparation")

print("WASM compatibility preparation completed successfully")

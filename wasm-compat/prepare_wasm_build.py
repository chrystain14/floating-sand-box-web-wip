from pathlib import Path
import os
import runpy
import tempfile
import urllib.request

# SFML 2.5.1's public Config.hpp rejects Emscripten even though the build
# configuration has already been taught about it. Patch that generated source
# before running the established compatibility preparation script.
sfml_config = Path("sfml-src/include/SFML/Config.hpp")
text = sfml_config.read_text(encoding="utf-8")
old = '''    #if defined(__ANDROID__)\n\n        // Android\n        #define SFML_SYSTEM_ANDROID\n\n    #elif defined(__linux__)'''
new = '''    #if defined(__ANDROID__)\n\n        // Android\n        #define SFML_SYSTEM_ANDROID\n\n    #elif defined(__EMSCRIPTEN__)\n\n        // Emscripten\n        #define SFML_SYSTEM_EMSCRIPTEN\n\n    #elif defined(__linux__)'''
if old not in text:
    raise RuntimeError("Could not locate SFML Config.hpp platform block")
sfml_config.write_text(text.replace(old, new, 1), encoding="utf-8")

# Run the last known-good compatibility preparation implementation from the
# exact commit that produced this staging build. Keeping it pinned prevents a
# moving remote dependency from silently changing the build.
url = "https://raw.githubusercontent.com/chrystain14/floating-sand-box-web-wip/da3d0e50138c1b2854cecf940167e067685ac89e/wasm-compat/prepare_wasm_build.py"
with urllib.request.urlopen(url, timeout=30) as response:
    original = response.read().decode("utf-8")

with tempfile.TemporaryDirectory(prefix="floating-sandbox-wasm-") as tmp:
    helper = Path(tmp) / "prepare_original.py"
    helper.write_text(original, encoding="utf-8")
    runpy.run_path(str(helper), run_name="__main__")

print("WASM compatibility preparation completed successfully")

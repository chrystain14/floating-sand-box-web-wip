from pathlib import Path
import runpy
import tempfile
import urllib.request

# Run the complete WebGL2 compatibility pass from the last diagnostic revision.
REV = "da3d0e50138c1b2854cecf940167e067685ac89e"
URL = f"https://raw.githubusercontent.com/chrystain14/floating-sand-box-web-wip/{REV}/wasm-compat/prepare_wasm_build.py"

with urllib.request.urlopen(URL, timeout=30) as response:
    original = response.read().decode("utf-8")

with tempfile.TemporaryDirectory(prefix="floating-sandbox-wasm-") as tmp:
    helper = Path(tmp) / "prepare_base.py"
    helper.write_text(original, encoding="utf-8")
    runpy.run_path(str(helper), run_name="__main__")

# SFML 2.5.1 tests __unix__ before it knows about Emscripten. Put the
# Emscripten branch BEFORE __unix__ so the compiler does not hit SFML's
# unsupported-UNIX error.
config_h = Path("sfml-src/include/SFML/Config.hpp")
text = config_h.read_text(encoding="utf-8")
marker = "#elif defined(__unix__)"
insert = """#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)\n\n    // Emscripten / WebAssembly\n    #define SFML_SYSTEM_EMSCRIPTEN\n\n#elif defined(__unix__)"""
if "#define SFML_SYSTEM_EMSCRIPTEN" not in text:
    if marker not in text:
        raise RuntimeError("Could not locate SFML __unix__ platform marker")
    text = text.replace(marker, insert, 1)
    config_h.write_text(text, encoding="utf-8")

final_text = config_h.read_text(encoding="utf-8")
if "#define SFML_SYSTEM_EMSCRIPTEN" not in final_text:
    raise RuntimeError("SFML Emscripten platform define was not applied")
if final_text.index("#define SFML_SYSTEM_EMSCRIPTEN") > final_text.index("#elif defined(__unix__)"):
    raise RuntimeError("SFML Emscripten platform branch was inserted after __unix__")

print("SFML Emscripten platform header patch verified")

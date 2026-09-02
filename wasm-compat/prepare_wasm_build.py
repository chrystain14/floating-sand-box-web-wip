from pathlib import Path
import runpy
import tempfile
import urllib.request

# Run the complete WebGL2 compatibility pass from the last complete revision.
REV = "706e49c3b0f01d4a635a9e940d6c990dbdf70e4d"
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
insert = """#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)

    // Emscripten / WebAssembly
    #define SFML_SYSTEM_EMSCRIPTEN

#elif defined(__unix__)"""
if "#define SFML_SYSTEM_EMSCRIPTEN" not in text:
    if marker not in text:
        raise RuntimeError("Could not locate SFML __unix__ platform marker")
    text = text.replace(marker, insert, 1)

# Some SFML 2.5.1 compiler paths still enter the nested UNIX detector under
# Emscripten. Patch that fallback explicitly so the browser build cannot hit
# SFML's unsupported-UNIX error even when the predefined macro is different.
unix_fallback = """        // Unsupported UNIX system\n        #error This UNIX operating system is not supported by SFML library"""
emscripten_fallback = """        // Emscripten / WebAssembly\n        #define SFML_SYSTEM_EMSCRIPTEN"""
if unix_fallback in text and "#define SFML_SYSTEM_EMSCRIPTEN" in text:
    text = text.replace(unix_fallback, emscripten_fallback, 1)

config_h.write_text(text, encoding="utf-8")

# Belt-and-suspenders: force the Emscripten macro through SFML's own CMake
# project too, so the header branch above is selected regardless of compiler
# predefined-macro behavior in the pinned Emscripten toolchain.
sfml_cmake = Path("sfml-src/CMakeLists.txt")
cmake_text = sfml_cmake.read_text(encoding="utf-8")
cmake_marker = "project(SFML)\n"
cmake_insert = "project(SFML)\nadd_definitions(-D__EMSCRIPTEN__)\n"
if "add_definitions(-D__EMSCRIPTEN__)" not in cmake_text:
    if cmake_marker not in cmake_text:
        raise RuntimeError("Could not locate SFML project() marker")
    cmake_text = cmake_text.replace(cmake_marker, cmake_insert, 1)
    sfml_cmake.write_text(cmake_text, encoding="utf-8")

final_text = config_h.read_text(encoding="utf-8")
if "#define SFML_SYSTEM_EMSCRIPTEN" not in final_text:
    raise RuntimeError("SFML Emscripten platform define was not applied")
if final_text.index("#define SFML_SYSTEM_EMSCRIPTEN") > final_text.index("#elif defined(__unix__)"):
    raise RuntimeError("SFML Emscripten platform branch was inserted after __unix__")
if "This UNIX operating system is not supported by SFML library" in final_text:
    raise RuntimeError("SFML UNIX fallback error was not removed for Emscripten")
if "add_definitions(-D__EMSCRIPTEN__)" not in sfml_cmake.read_text(encoding="utf-8"):
    raise RuntimeError("SFML CMake Emscripten definition was not applied")

print("SFML Emscripten platform header and CMake patches verified")

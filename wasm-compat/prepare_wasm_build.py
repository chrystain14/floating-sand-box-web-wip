from pathlib import Path
import re
import runpy
import tempfile
import urllib.request

# Reuse the last complete compatibility pass, then apply the SFML 2.5.1
# Emscripten platform fix deterministically.
REV = "706e49c3b0f01d4a635a9e940d6c990dbdf70e4d"
URL = f"https://raw.githubusercontent.com/chrystain14/floating-sand-box-web-wip/{REV}/wasm-compat/prepare_wasm_build.py"

with urllib.request.urlopen(URL, timeout=30) as response:
    original = response.read().decode("utf-8")

with tempfile.TemporaryDirectory(prefix="floating-sandbox-wasm-") as tmp:
    helper = Path(tmp) / "prepare_base.py"
    helper.write_text(original, encoding="utf-8")
    runpy.run_path(str(helper), run_name="__main__")

config_h = Path("sfml-src/include/SFML/Config.hpp")
text = config_h.read_text(encoding="utf-8")
start_marker = "#if defined(_WIN32)"
end_marker = "////////////////////////////////////////////////////////////\n// Define a portable debug macro"
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("Could not locate SFML Config.hpp platform-detection block")
platform_block = r'''#if defined(_WIN32)

    // Windows
    #define SFML_SYSTEM_WINDOWS
    #ifndef NOMINMAX
        #define NOMINMAX
    #endif

#elif defined(__APPLE__) && defined(__MACH__)

    // Apple platform, see which one it is
    #include "TargetConditionals.h"

    #if TARGET_OS_IPHONE || TARGET_IPHONE_SIMULATOR

        // iOS
        #define SFML_SYSTEM_IOS

    #elif TARGET_OS_MAC

        // MacOS
        #define SFML_SYSTEM_MACOS

    #else

        // Unsupported Apple system
        #error This Apple operating system is not supported by SFML library

    #endif

#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)

    // Emscripten / WebAssembly
    #define SFML_SYSTEM_EMSCRIPTEN

#elif defined(__unix__)

    // UNIX system, see which one it is
    #if defined(__ANDROID__)

        // Android
        #define SFML_SYSTEM_ANDROID

    #elif defined(__linux__)

         // Linux
        #define SFML_SYSTEM_LINUX

    #elif defined(__FreeBSD__) || defined(__FreeBSD_kernel__)

        // FreeBSD
        #define SFML_SYSTEM_FREEBSD

    #elif defined(__OpenBSD__)

        // OpenBSD
        #define SFML_SYSTEM_OPENBSD

    #else

        // Unsupported UNIX system
        #error This UNIX operating system is not supported by SFML library

    #endif

#else

    // Unsupported system
    #error This operating system is not supported by SFML library

#endif


'''
text = text[:start] + platform_block + text[end:]
config_h.write_text(text, encoding="utf-8")

# Force the same macro at CMake level as well, so every SFML translation unit
# sees the Emscripten platform consistently under Emscripten 3.1.12.
sfml_cmake = Path("sfml-src/CMakeLists.txt")
cmake_text = sfml_cmake.read_text(encoding="utf-8")
if "add_definitions(-D__EMSCRIPTEN__)" not in cmake_text:
    m = re.search(r"project\(SFML\)\s*\n", cmake_text)
    if not m:
        raise RuntimeError("Could not locate SFML project() declaration")
    cmake_text = cmake_text[:m.end()] + "add_definitions(-D__EMSCRIPTEN__)\n" + cmake_text[m.end():]
    sfml_cmake.write_text(cmake_text, encoding="utf-8")

final_text = config_h.read_text(encoding="utf-8")
branch_pos = final_text.find("#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)")
unix_pos = final_text.find("#elif defined(__unix__)")
if branch_pos < 0 or unix_pos < 0 or branch_pos >= unix_pos:
    raise RuntimeError("SFML Emscripten branch is not before the UNIX branch")
if "#define SFML_SYSTEM_EMSCRIPTEN" not in final_text:
    raise RuntimeError("SFML Emscripten platform define was not applied")
if "This UNIX operating system is not supported by SFML library" not in final_text:
    raise RuntimeError("SFML Config.hpp unexpectedly lost its UNIX guard")
if "add_definitions(-D__EMSCRIPTEN__)" not in sfml_cmake.read_text(encoding="utf-8"):
    raise RuntimeError("SFML CMake Emscripten definition was not applied")

print("SFML Emscripten platform detection patched and verified")

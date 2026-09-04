from pathlib import Path
import os
import re
import runpy

# Keep Emscripten's platform macro explicit for every SFML compile.
for var in ("CFLAGS", "CXXFLAGS"):
    current = os.environ.get(var, "")
    if "-D__EMSCRIPTEN__" not in current:
        os.environ[var] = (current + " -D__EMSCRIPTEN__").strip()

# Reuse the complete compatibility pass already established on the staging
# branch, including the wxWidgets/OpenGL/SFML dependency shims.
runpy.run_path(str(Path(__file__).with_name("prepare_wasm_build_base.py")), run_name="__main__")

# SFML 2.5.1's Config.hpp platform block is the critical part. Replace the
# entire block instead of relying on fragile single-line insertion. Emscripten
# MUST be checked before __unix__, because Clang defines both.
config_h = Path("sfml-src/include/SFML/Config.hpp")
text = config_h.read_text(encoding="utf-8")
start_marker = "#if defined(_WIN32)"
end_marker = "////////////////////////////////////////////////////////////\n// Define a portable debug macro"
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("Could not locate SFML Config.hpp platform-detection block")

platform_block = '''#if defined(_WIN32)\n\n    // Windows\n    #define SFML_SYSTEM_WINDOWS\n    #ifndef NOMINMAX\n        #define NOMINMAX\n    #endif\n\n#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)\n\n    // Emscripten / WebAssembly\n    #define SFML_SYSTEM_EMSCRIPTEN\n\n#elif defined(__APPLE__) && defined(__MACH__)\n\n    // Apple platform, see which one it is\n    #include "TargetConditionals.h"\n\n    #if TARGET_OS_IPHONE || TARGET_IPHONE_SIMULATOR\n\n        // iOS\n        #define SFML_SYSTEM_IOS\n\n    #elif TARGET_OS_MAC\n\n        // MacOS\n        #define SFML_SYSTEM_MACOS\n\n    #else\n\n        // Unsupported Apple system\n        #error This Apple operating system is not supported by SFML library\n\n    #endif\n\n#elif defined(__unix__)\n\n    // UNIX system, see which one it is\n    #if defined(__ANDROID__)\n\n        // Android\n        #define SFML_SYSTEM_ANDROID\n\n    #elif defined(__linux__)\n\n        // Linux\n        #define SFML_SYSTEM_LINUX\n\n    #elif defined(__FreeBSD__) || defined(__FreeBSD_kernel__)\n\n        // FreeBSD\n        #define SFML_SYSTEM_FREEBSD\n\n    #elif defined(__OpenBSD__)\n\n        // OpenBSD\n        #define SFML_SYSTEM_OPENBSD\n\n    #else\n\n        // Unsupported UNIX system\n        #error This UNIX operating system is not supported by SFML library\n\n    #endif\n\n#else\n\n    // Unsupported system\n    #error This operating system is not supported by SFML library\n\n#endif\n\n\n'''

text = text[:start] + platform_block + text[end:]
config_h.write_text(text, encoding="utf-8")

# Force the matching compiler definition at SFML's CMake level too.
sfml_cmake = Path("sfml-src/CMakeLists.txt")
cmake_text = sfml_cmake.read_text(encoding="utf-8")
if "add_definitions(-D__EMSCRIPTEN__)" not in cmake_text:
    m = re.search(r"project\\(SFML\\)\\s*\\n", cmake_text)
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

print("Deterministic SFML Emscripten platform patch verified")

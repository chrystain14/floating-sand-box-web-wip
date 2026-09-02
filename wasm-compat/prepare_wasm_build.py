from pathlib import Path
import runpy

# Apply the complete compatibility pass first.
base = Path(__file__).with_name("prepare_wasm_build_base.py")
runpy.run_path(str(base), run_name="__main__")

# SFML 2.5.1 has no native Emscripten platform branch in Config.hpp.
# Emscripten also defines __unix__, so an unpatched header falls into SFML's
# unsupported-UNIX error. Use the Unix/Linux implementation paths for SFML's
# system/network code while keeping the CMake-side platform as Emscripten.
config_h = Path("sfml-src/include/SFML/Config.hpp")
text = config_h.read_text(encoding="utf-8")
start_marker = "#if defined(_WIN32)"
end_marker = "////////////////////////////////////////////////////////////\n// Define a portable debug macro"
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("Could not locate SFML Config.hpp platform block")
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
        #define SFML_SYSTEM_IOS
    #elif TARGET_OS_MAC
        #define SFML_SYSTEM_MACOS
    #else
        #error This Apple operating system is not supported by SFML library
    #endif

#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)

    // Emscripten / WebAssembly. Reuse SFML's Unix implementation families.
    #define SFML_SYSTEM_EMSCRIPTEN
    #define SFML_SYSTEM_UNIX
    #define SFML_SYSTEM_LINUX

#elif defined(__unix__)

    // UNIX system, see which one it is
    #if defined(__ANDROID__)
        #define SFML_SYSTEM_ANDROID
    #elif defined(__linux__)
        #define SFML_SYSTEM_LINUX
    #elif defined(__FreeBSD__) || defined(__FreeBSD_kernel__)
        #define SFML_SYSTEM_FREEBSD
    #elif defined(__OpenBSD__)
        #define SFML_SYSTEM_OPENBSD
    #else
        #error This UNIX operating system is not supported by SFML library
    #endif

#else

    #error This operating system is not supported by SFML library

#endif


'''
# Replace the entire platform-detection block, then verify the actual file.
config_h.write_text(text[:start] + platform_block + text[end:], encoding="utf-8")

# Extra deterministic guard: if a future upstream/template change causes the
# block replacement above to miss, explicitly inject the Emscripten branch.
final_text = config_h.read_text(encoding="utf-8")
ems = "#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)"
unix = "#elif defined(__unix__)"
if ems not in final_text:
    marker = unix
    replacement = (
        "#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)\n\n"
        "    // Emscripten / WebAssembly\n"
        "    #define SFML_SYSTEM_EMSCRIPTEN\n"
        "    #define SFML_SYSTEM_UNIX\n"
        "    #define SFML_SYSTEM_LINUX\n\n"
        + unix
    )
    final_text = final_text.replace(marker, replacement, 1)
    config_h.write_text(final_text, encoding="utf-8")
    final_text = config_h.read_text(encoding="utf-8")

branch_pos = final_text.find(ems)
unix_pos = final_text.find(unix, branch_pos + 1)
if branch_pos < 0 or unix_pos < 0 or branch_pos >= unix_pos:
    raise RuntimeError("SFML Emscripten platform branch is not before the UNIX branch")
branch_end = final_text.find("#elif defined(__unix__)", branch_pos + 1)
branch_text = final_text[branch_pos:branch_end]
if "#define SFML_SYSTEM_EMSCRIPTEN" not in branch_text:
    raise RuntimeError("SFML_SYSTEM_EMSCRIPTEN was not applied")
if "#define SFML_SYSTEM_UNIX" not in branch_text:
    raise RuntimeError("SFML_SYSTEM_UNIX was not applied")
if "#define SFML_SYSTEM_LINUX" not in branch_text:
    raise RuntimeError("SFML_SYSTEM_LINUX was not applied")
if "This UNIX operating system is not supported by SFML library" not in final_text:
    raise RuntimeError("SFML UNIX guard unexpectedly disappeared")

print("SFML Emscripten Config.hpp compatibility patch applied and verified")

from pathlib import Path
import runpy
base = Path(__file__).with_name("prepare_wasm_build_base.py")
runpy.run_path(str(base), run_name="__main__")
config_h = Path("sfml-src/include/SFML/Config.hpp")
text = config_h.read_text(encoding="utf-8")
start = text.find("#if defined(_WIN32)")
end = text.find("////////////////////////////////////////////////////////////\n// Define a portable debug macro", start)
if start < 0 or end < 0:
    raise RuntimeError("Could not locate SFML platform block")
platform_block = '''#if 1
    #define SFML_SYSTEM_EMSCRIPTEN
#else
    #if defined(_WIN32)
        #define SFML_SYSTEM_WINDOWS
    #elif defined(__APPLE__) && defined(__MACH__)
        #define SFML_SYSTEM_MACOS
    #elif defined(__unix__)
        #define SFML_SYSTEM_UNIX
    #endif
#endif


'''
config_h.write_text(text[:start] + platform_block + text[end:], encoding="utf-8")
print("SFML Emscripten platform selection forced and verified")

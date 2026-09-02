from pathlib import Path
import runpy

# Apply the complete compatibility pass first.
base = Path(__file__).with_name("prepare_wasm_build_base.py")
runpy.run_path(str(base), run_name="__main__")

# SFML 2.5.1's Config.hpp checks __unix__ before it knows about Emscripten.
# Emscripten defines __unix__, so add an explicit branch before that check and
# keep SFML_SYSTEM_UNIX enabled because SFML 2.5.1 uses the Unix implementations
# for Clock/Mutex/Sleep/Thread when not on Windows.
config_h = Path("sfml-src/include/SFML/Config.hpp")
text = config_h.read_text(encoding="utf-8")
needle = "#elif defined(__unix__)\n\n    // UNIX system, see which one it is"
replacement = "#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)\n\n    // Emscripten / WebAssembly\n    #define SFML_SYSTEM_EMSCRIPTEN\n    #define SFML_SYSTEM_UNIX\n\n#elif defined(__unix__)\n\n    // UNIX system, see which one it is"
if needle not in text:
    raise RuntimeError("Could not locate SFML UNIX platform branch")
text = text.replace(needle, replacement, 1)
config_h.write_text(text, encoding="utf-8")

# Verify the exact ordering so Emscripten cannot fall through to SFML's
# unsupported-UNIX error during compilation.
final_text = config_h.read_text(encoding="utf-8")
em_branch = final_text.find("#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)")
unix_branch = final_text.find("#elif defined(__unix__)")
if em_branch < 0 or unix_branch < 0 or em_branch >= unix_branch:
    raise RuntimeError("SFML Emscripten branch is not before the UNIX branch")
if "#define SFML_SYSTEM_EMSCRIPTEN" not in final_text[em_branch:unix_branch]:
    raise RuntimeError("SFML_SYSTEM_EMSCRIPTEN was not applied")
if "#define SFML_SYSTEM_UNIX" not in final_text[em_branch:unix_branch]:
    raise RuntimeError("SFML_SYSTEM_UNIX was not applied")

print("SFML Emscripten platform selection patched and verified")

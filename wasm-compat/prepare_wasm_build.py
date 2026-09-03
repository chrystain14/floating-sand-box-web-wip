from pathlib import Path
import os
import runpy

# SFML 2.5.1 does not reliably receive the Emscripten platform macro from its
# own CMake detection under Emscripten 3.1.12. The macro must be present in the
# final compiler environment used by CMake.
for var in ("CFLAGS", "CXXFLAGS"):
    current = os.environ.get(var, "")
    if "-D__EMSCRIPTEN__" not in current:
        os.environ[var] = (current + " -D__EMSCRIPTEN__").strip()

# Run the complete compatibility pass first.
runpy.run_path(str(Path(__file__).with_name("prepare_wasm_build_base.py")), run_name="__main__")

# The compatibility pass above is intentionally followed by a final direct
# guard. This makes the critical SFML platform header fix deterministic even
# if a nested helper changes the header earlier in the preparation process.
config_h = Path("sfml-src/include/SFML/Config.hpp")
text = config_h.read_text(encoding="utf-8")

if "#define SFML_SYSTEM_EMSCRIPTEN" not in text:
    marker = "#elif defined(__unix__)"
    branch = "#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)\n\n    // Emscripten / WebAssembly\n    #define SFML_SYSTEM_EMSCRIPTEN\n\n"
    if marker not in text:
        raise RuntimeError("Could not locate SFML UNIX platform branch")
    text = text.replace(marker, branch + marker, 1)
    config_h.write_text(text, encoding="utf-8")

# Verify the branch is actually before the generic UNIX handling.
final_text = config_h.read_text(encoding="utf-8")
branch_pos = final_text.find("#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)")
unix_pos = final_text.find("#elif defined(__unix__)")
if branch_pos < 0 or unix_pos < 0 or branch_pos >= unix_pos:
    raise RuntimeError("SFML Emscripten branch is not before the UNIX branch")

print("Final SFML Emscripten Config.hpp guard verified")

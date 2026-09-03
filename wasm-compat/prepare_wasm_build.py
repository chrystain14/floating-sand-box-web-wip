from pathlib import Path
import runpy

# Keep the main entry point wired to the complete compatibility pass. That
# pass restores the SFML 2.5.1 WebAssembly patches and applies the Emscripten
# platform fix before the SFML build begins.

runpy.run_path(str(Path(__file__).with_name("prepare_wasm_build_base.py")), run_name="__main__")

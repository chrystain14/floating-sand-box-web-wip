from pathlib import Path
import os
import re
import runpy
import tempfile
import urllib.request

# Reuse the known-good compatibility preparation from the last stable
# staging point, then apply the Emscripten/WebGL2 fixes needed by the current
# Floating Sandbox build.
url = "https://raw.githubusercontent.com/chrystain14/floating-sand-box-web-wip/5dad57eb1479d91af16e6e85cd444f144671a171/wasm-compat/prepare_wasm_build.py"
with urllib.request.urlopen(url, timeout=30) as response:
    original = response.read().decode("utf-8")

with tempfile.TemporaryDirectory(prefix="floating-sandbox-wasm-") as tmp:
    helper = Path(tmp) / "prepare_original.py"
    helper.write_text(original, encoding="utf-8")
    runpy.run_path(str(helper), run_name="__main__")

FS_ROOT = Path("upstream-floating-sandbox")
SFML_ROOT = Path("sfml-src")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text was not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_function(path: Path, function_name: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.find(function_name)
    if start < 0:
        raise RuntimeError(f"Could not find function {function_name} in {path}")
    brace = text.find("{", start)
    if brace < 0:
        raise RuntimeError(f"Could not find function body for {function_name} in {path}")
    depth = 0
    end = None
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise RuntimeError(f"Could not match braces for {function_name} in {path}")
    path.write_text(text[:brace] + replacement + text[end:], encoding="utf-8")


# ---------------------------------------------------------------------------
# SFML 2.5.1 public headers: the previous run proved that CMake was configured
# correctly, but Config.hpp rejected Emscripten as an unknown UNIX platform.
# Put the Emscripten branch before the __unix__ branch.
# ---------------------------------------------------------------------------
config_h = SFML_ROOT / "include/SFML/Config.hpp"
text = config_h.read_text(encoding="utf-8")
if "#define SFML_SYSTEM_EMSCRIPTEN" not in text:
    old = '#elif defined(__APPLE__) && defined(__MACH__)'
    new = '''#elif defined(__EMSCRIPTEN__) || defined(EMSCRIPTEN)\n\n    // Emscripten / WebAssembly\n    #define SFML_SYSTEM_EMSCRIPTEN\n\n#elif defined(__APPLE__) && defined(__MACH__)'''
    if old not in text:
        raise RuntimeError("Could not locate SFML Config.hpp Apple branch")
    config_h.write_text(text.replace(old, new, 1), encoding="utf-8")

# Keep the original SFML platform patch and install-directory patch idempotent
# even if the helper implementation changes later.
sfml_config_cmake = SFML_ROOT / "cmake/Config.cmake"
cmake_text = sfml_config_cmake.read_text(encoding="utf-8")
if "STREQUAL \"Emscripten\"" not in cmake_text:
    old = 'elseif(${CMAKE_SYSTEM_NAME} STREQUAL "Darwin")'
    new = '''elseif(${CMAKE_SYSTEM_NAME} STREQUAL "Emscripten")\n    set(SFML_OS_UNIX 1)\n    set(SFML_OS_EMSCRIPTEN 1)\n    set(OPENGL_ES 1)\nelseif(${CMAKE_SYSTEM_NAME} STREQUAL "Darwin")'''
    if old not in cmake_text:
        raise RuntimeError("Could not locate SFML CMake platform branch")
    sfml_config_cmake.write_text(cmake_text.replace(old, new, 1), encoding="utf-8")

patched = config_h.read_text(encoding="utf-8")
if "#define SFML_SYSTEM_EMSCRIPTEN" not in patched:
    raise RuntimeError("SFML Emscripten platform define is missing")

# ---------------------------------------------------------------------------
# Floating Sandbox shader conversion.
# We convert the shipped shader syntax in the fresh upstream clone. Keeping the
# marker lines at ###VERTEX-120 / ###FRAGMENT-120 lets the existing preprocessor
# split the files exactly as before; the C++ patch below upgrades the emitted
# GLSL version to WebGL2 and adds fragment precision/output declarations.
# ---------------------------------------------------------------------------
def convert_shader_files(shader_root: Path) -> None:
    changed = 0
    visited = 0
    for path in sorted(shader_root.rglob("*")):
        if not path.is_file() or path.suffix not in {".glsl", ".glslinc"}:
            continue
        visited += 1
        source = path.read_text(encoding="utf-8")
        updated = source
        updated = re.sub(r"^\s*#define\s+in\s+attribute\s*$", "", updated, flags=re.MULTILINE)
        updated = re.sub(r"^\s*#define\s+out\s+varying\s*$", "", updated, flags=re.MULTILINE)
        updated = re.sub(r"^\s*#define\s+in\s+varying\s*$", "", updated, flags=re.MULTILINE)
        updated = updated.replace("texture2D(", "texture(")
        updated = updated.replace("texture2DLod(", "textureLod(")
        updated = updated.replace("textureCube(", "texture(")
        updated = updated.replace("gl_FragColor", "fsOutColor")
        if updated != source:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    print(f"Converted {visited} shader files ({changed} changed)")
    if visited == 0:
        raise RuntimeError(f"No shader files found under {shader_root}")


convert_shader_files(FS_ROOT / "Data/Shaders")

# ---------------------------------------------------------------------------
# ShaderManager: emit genuine GLSL ES 3.00 regardless of the legacy marker.
# Precision/output declarations must come immediately after #version, before
# common code or resolved includes are inserted.
# ---------------------------------------------------------------------------
shader_manager = FS_ROOT / "Sources/OpenGLCore/ShaderManager.cpp.inl"
replace_once(
    shader_manager,
    '            vertexShaderCode << "#version " << match[1].str() << sSource.widen(\'\\n\');',
    '''#ifdef __EMSCRIPTEN__\n            vertexShaderCode << "#version 300 es" << sSource.widen('\\n');\n#else\n            vertexShaderCode << "#version " << match[1].str() << sSource.widen('\\n');\n#endif''',
)
replace_once(
    shader_manager,
    '             fragmentShaderCode << "#version " << match[1].str() << sSource.widen(\'\\n\');',
    '''#ifdef __EMSCRIPTEN__\n            fragmentShaderCode << "#version 300 es" << sSource.widen('\\n');\n            fragmentShaderCode << "precision highp float;" << sSource.widen('\\n');\n            fragmentShaderCode << "precision highp int;" << sSource.widen('\\n');\n            fragmentShaderCode << "layout(location = 0) out vec4 fsOutColor;" << sSource.widen('\\n');\n#else\n            fragmentShaderCode << "#version " << match[1].str() << sSource.widen('\\n');\n#endif''',
)

# ---------------------------------------------------------------------------
# GameOpenGL: WebGL2 is GLES 3.0, while the desktop minimum-version check is
# written for desktop OpenGL. Skip only that comparison on Emscripten.
# ---------------------------------------------------------------------------
replace_once(
    FS_ROOT / "Sources/OpenGLCore/GameOpenGL.cpp",
    '''    if (GLVersion.major < MinOpenGLVersionMaj\n        || (GLVersion.major == MinOpenGLVersionMaj && GLVersion.minor < MinOpenGLVersionMin))\n    {\n        throw GameException(\n            std::string("We are sorry, but this game requires at least OpenGL ")\n            + std::to_string(MinOpenGLVersionMaj) + "." + std::to_string(MinOpenGLVersionMin)\n            + ", while the version currently supported by your graphics driver is "\n            + std::to_string(GLVersion.major) + "." + std::to_string(GLVersion.minor) + "."\n            + " Check whether a more recent driver is available for your system.");\n    }''',
    '''#ifndef __EMSCRIPTEN__\n    if (GLVersion.major < MinOpenGLVersionMaj\n        || (GLVersion.major == MinOpenGLVersionMaj && GLVersion.minor < MinOpenGLVersionMin))\n    {\n        throw GameException(\n            std::string("We are sorry, but this game requires at least OpenGL ")\n            + std::to_string(MinOpenGLVersionMaj) + "." + std::to_string(MinOpenGLVersionMin)\n            + ", while the version currently supported by your graphics driver is "\n            + std::to_string(GLVersion.major) + "." + std::to_string(GLVersion.minor) + "."\n            + " Check whether a more recent driver is available for your system.");\n    }\n#endif''',
)

# ---------------------------------------------------------------------------
# GameOpenGL_Ext: WebGL2 provides the modern entry points as core GLES, not
# desktop ARB/EXT names. Load only APIs that actually exist in WebGL2 here;
# GPUCalc is intentionally not part of the game target.
# ---------------------------------------------------------------------------
ext = FS_ROOT / "Sources/OpenGLCore/GameOpenGL_Ext.cpp"
replace_function(
    ext,
    "void InitOpenGLExt_Framebuffer(GLADloadproc load)",
    '''{\n#ifdef __EMSCRIPTEN__\n    LoadAndVerify("glIsRenderbuffer", glIsRenderbuffer, load);\n    LoadAndVerify("glBindRenderbuffer", glBindRenderbuffer, load);\n    LoadAndVerify("glDeleteRenderbuffers", glDeleteRenderbuffers, load);\n    LoadAndVerify("glGenRenderbuffers", glGenRenderbuffers, load);\n    LoadAndVerify("glRenderbufferStorage", glRenderbufferStorage, load);\n    LoadAndVerify("glGetRenderbufferParameteriv", glGetRenderbufferParameteriv, load);\n    LoadAndVerify("glIsFramebuffer", glIsFramebuffer, load);\n    LoadAndVerify("glBindFramebuffer", glBindFramebuffer, load);\n    LoadAndVerify("glDeleteFramebuffers", glDeleteFramebuffers, load);\n    LoadAndVerify("glGenFramebuffers", glGenFramebuffers, load);\n    LoadAndVerify("glCheckFramebufferStatus", glCheckFramebufferStatus, load);\n    LoadAndVerify("glFramebufferTexture2D", glFramebufferTexture2D, load);\n    LoadAndVerify("glFramebufferRenderbuffer", glFramebufferRenderbuffer, load);\n    LoadAndVerify("glGetFramebufferAttachmentParameteriv", glGetFramebufferAttachmentParameteriv, load);\n    // WebGL2 has no glFramebufferTexture1D/glFramebufferTexture3D entry points.\n    return;\n#else\n    if (GLVersion.major >= 3) // Core in 3.0\n    {\n        // Core\n\n        LoadAndVerify("glIsRenderbuffer", glIsRenderbuffer, load);\n        LoadAndVerify("glIsRenderbuffer", glIsRenderbuffer, load);\n        LoadAndVerify("glBindRenderbuffer", glBindRenderbuffer, load);\n        LoadAndVerify("glDeleteRenderbuffers", glDeleteRenderbuffers, load);\n        LoadAndVerify("glGenRenderbuffers", glGenRenderbuffers, load);\n        LoadAndVerify("glRenderbufferStorage", glRenderbufferStorage, load);\n        LoadAndVerify("glGetRenderbufferParameteriv", glGetRenderbufferParameteriv, load);\n        LoadAndVerify("glIsFramebuffer", glIsFramebuffer, load);\n        LoadAndVerify("glBindFramebuffer", glBindFramebuffer, load);\n        LoadAndVerify("glDeleteFramebuffers", glDeleteFramebuffers, load);\n        LoadAndVerify("glGenFramebuffers", glGenFramebuffers, load);\n        LoadAndVerify("glCheckFramebufferStatus", glCheckFramebufferStatus, load);\n        LoadAndVerify("glFramebufferTexture1D", glFramebufferTexture1D, load);\n        LoadAndVerify("glFramebufferTexture2D", glFramebufferTexture2D, load);\n        LoadAndVerify("glFramebufferTexture3D", glFramebufferTexture3D, load);\n        LoadAndVerify("glFramebufferRenderbuffer", glFramebufferRenderbuffer, load);\n        LoadAndVerify("glGetFramebufferAttachmentParameteriv", glGetFramebufferAttachmentParameteriv, load);\n    }\n    else if (HasExt("GL_EXT_framebuffer_object"))\n    {\n        LoadAndVerify("glIsRenderbufferEXT", glIsRenderbuffer, load);\n        LoadAndVerify("glIsRenderbufferEXT", glIsRenderbuffer, load);\n        LoadAndVerify("glBindRenderbufferEXT", glBindRenderbuffer, load);\n        LoadAndVerify("glDeleteRenderbuffersEXT", glDeleteRenderbuffers, load);\n        LoadAndVerify("glGenRenderbuffersEXT", glGenRenderbuffers, load);\n        LoadAndVerify("glRenderbufferStorageEXT", glRenderbufferStorage, load);\n        LoadAndVerify("glGetRenderbufferParameterivEXT", glGetRenderbufferParameteriv, load);\n        LoadAndVerify("glIsFramebufferEXT", glIsFramebuffer, load);\n        LoadAndVerify("glBindFramebufferEXT", glBindFramebuffer, load);\n        LoadAndVerify("glDeleteFramebuffersEXT", glDeleteFramebuffers, load);\n        LoadAndVerify("glGenFramebuffersEXT", glGenFramebuffers, load);\n        LoadAndVerify("glCheckFramebufferStatusEXT", glCheckFramebufferStatus, load);\n        LoadAndVerify("glFramebufferTexture1DEXT", glFramebufferTexture1D, load);\n        LoadAndVerify("glFramebufferTexture2DEXT", glFramebufferTexture2D, load);\n        LoadAndVerify("glFramebufferTexture3DEXT", glFramebufferTexture3D, load);\n        LoadAndVerify("glFramebufferRenderbufferEXT", glFramebufferRenderbuffer, load);\n        LoadAndVerify("glGetFramebufferAttachmentParameterivEXT", glGetFramebufferAttachmentParameteriv, load);\n    }\n    else\n    {\n        throw GameException("Framebuffer functionality is not supported");\n    }\n#endif\n}''',
)
replace_function(
    ext,
    "void InitOpenGLExt_DrawInstanced(GLADloadproc load)",
    '''{\n#ifdef __EMSCRIPTEN__\n    LoadAndVerify("glDrawArraysInstanced", glDrawArraysInstanced, load);\n    LoadAndVerify("glDrawElementsInstanced", glDrawElementsInstanced, load);\n    return;\n#else\n    if (GLVersion.major > 3\n        || (GLVersion.major == 3 && GLVersion.minor >= 1))\n    {\n        LoadAndVerify("glDrawArraysInstanced", glDrawArraysInstanced, load);\n        LoadAndVerify("glDrawElementsInstanced", glDrawElementsInstanced, load);\n    }\n    else if (HasExt("GL_ARB_draw_instanced"))\n    {\n        LoadAndVerify("glDrawArraysInstancedARB", glDrawArraysInstanced, load);\n        LoadAndVerify("glDrawElementsInstancedARB", glDrawElementsInstanced, load);\n    }\n    else if (HasExt("GL_EXT_draw_instanced"))\n    {\n        LoadAndVerify("glDrawArraysInstancedEXT", glDrawArraysInstanced, load);\n        LoadAndVerify("glDrawElementsInstancedEXT", glDrawElementsInstanced, load);\n    }\n    else\n    {\n        throw GameException("Instanced Drawing functionality is not supported");\n    }\n#endif\n}''',
)
replace_function(
    ext,
    "void InitOpenGLExt_VertexArray(GLADloadproc load)",
    '''{\n#ifdef __EMSCRIPTEN__\n    LoadAndVerify("glBindVertexArray", glBindVertexArray, load);\n    LoadAndVerify("glDeleteVertexArrays", glDeleteVertexArrays, load);\n    LoadAndVerify("glGenVertexArrays", glGenVertexArrays, load);\n    LoadAndVerify("glIsVertexArray", glIsVertexArray, load);\n    return;\n#else\n    if (GLVersion.major >= 3 || HasExt("GL_ARB_vertex_array_object"))\n    {\n        LoadAndVerify("glBindVertexArray", glBindVertexArray, load);\n        LoadAndVerify("glDeleteVertexArrays", glDeleteVertexArrays, load);\n        LoadAndVerify("glGenVertexArrays", glGenVertexArrays, load);\n        LoadAndVerify("glIsVertexArray", glIsVertexArray, load);\n    }\n    else if (HasExt("GL_APPLE_vertex_array_object"))\n    {\n        LoadAndVerify("glBindVertexArrayAPPLE", glBindVertexArray, load);\n        LoadAndVerify("glDeleteVertexArraysAPPLE", glDeleteVertexArrays, load);\n        LoadAndVerify("glGenVertexArraysAPPLE", glGenVertexArrays, load);\n        LoadAndVerify("glIsVertexArrayAPPLE", glIsVertexArray, load);\n    }\n    else\n    {\n        throw GameException("VAO functionality is not supported");\n    }\n#endif\n}''',
)
replace_function(
    ext,
    "void InitOpenGLExt_TextureFloat(GLADloadproc /*load*/)",
    '''{\n#ifdef __EMSCRIPTEN__\n    return;\n#else\n    if (GLVersion.major >= 3 || HasExt("GL_ARB_texture_float"))\n    {\n    }\n    else\n    {\n        throw GameException("Texture Float functionality is not supported");\n    }\n#endif\n}''',
)
replace_function(
    ext,
    "void InitOpenGLExt_TextureRG(GLADloadproc /*load*/)",
    '''{\n#ifdef __EMSCRIPTEN__\n    return;\n#else\n    if (GLVersion.major >= 3 || HasExt("GL_ARB_texture_rg"))\n    {\n    }\n    else\n    {\n        throw GameException("Texture RG functionality is not supported");\n    }\n#endif\n}''',
)
replace_function(
    ext,
    "void InitOpenGLExt_Misc(GLADloadproc load)",
    '''{\n#ifdef __EMSCRIPTEN__\n    glGetProgramBinary = nullptr;\n    glDebugMessageCallback = nullptr;\n    return;\n#else\n    if (GLVersion.major > 4 || (GLVersion.major == 4 && GLVersion.minor >= 1))\n    {\n        LoadAndVerify("glGetProgramBinary", glGetProgramBinary, load);\n    }\n    else if (HasExt("GL_ARB_get_program_binary"))\n    {\n        LoadAndVerify("glGetProgramBinary", glGetProgramBinary, load);\n    }\n\n    if (HasExt("GL_ARB_debug_output"))\n    {\n        LoadAndVerify("glDebugMessageCallbackARB", glDebugMessageCallback, load);\n    }\n#endif\n}''',
)
replace_function(
    ext,
    "void InitOpenGLExt()",
    '''{\n    try\n    {\n#ifdef __EMSCRIPTEN__\n        if (open_gl())\n        {\n            InitOpenGLExt_Framebuffer(&get_proc);\n            InitOpenGLExt_DrawInstanced(&get_proc);\n            InitOpenGLExt_VertexArray(&get_proc);\n            InitOpenGLExt_TextureFloat(&get_proc);\n            InitOpenGLExt_TextureRG(&get_proc);\n            InitOpenGLExt_Misc(&get_proc);\n            close_gl();\n        }\n#else\n        if (open_gl())\n        {\n            if (get_exts())\n            {\n                InitOpenGLExt_Framebuffer(&get_proc);\n                InitOpenGLExt_DrawInstanced(&get_proc);\n                InitOpenGLExt_VertexArray(&get_proc);\n                InitOpenGLExt_TextureFloat(&get_proc);\n                InitOpenGLExt_TextureRG(&get_proc);\n                InitOpenGLExt_Misc(&get_proc);\n                free_exts();\n            }\n            close_gl();\n        }\n#endif\n    }\n    catch (std::exception const & ex)\n    {\n        throw GameException(\n            std::string("We are sorry, but this game requires OpenGL functionality which your graphics driver appears to not support;")\n            + " the error is: " + ex.what());\n    }\n}''',
)

# ---------------------------------------------------------------------------
# WebGL has no glMapBuffer/glUnmapBuffer. Replace the three streaming-map
# sites with persistent CPU byte/vertex buffers and glBufferSubData().
# ---------------------------------------------------------------------------
render_h = FS_ROOT / "Sources/Render/ShipRenderContext.h"
replace_once(
    render_h,
    '    GameOpenGLVBO mPointAttributeGroupVBO; // Light, water, temperature, rot, rust, algae growth\n',
    '    GameOpenGLVBO mPointAttributeGroupVBO; // Light, water, temperature, rot, rust, algae growth\n    std::vector<PointAttributeGroupVertex> mPointAttributeGroupCpuBuffer;\n',
)
replace_once(
    render_h,
    '    GameOpenGLVBO mGenericMipMappedTextureVBO;\n',
    '    GameOpenGLVBO mGenericMipMappedTextureVBO;\n    std::vector<uint8_t> mGenericMipMappedTextureCpuBuffer;\n',
)
replace_once(
    render_h,
    '    GameOpenGLVBO mExplosionVBO;\n',
    '    GameOpenGLVBO mExplosionVBO;\n    std::vector<uint8_t> mExplosionCpuBuffer;\n',
)

render_cpp = FS_ROOT / "Sources/Render/ShipRenderContext.cpp"
replace_once(
    render_cpp,
    '''    PointAttributeGroupVertex * const restrict pDst = reinterpret_cast<PointAttributeGroupVertex *>(glMapBuffer(GL_ARRAY_BUFFER, GL_WRITE_ONLY));\n    CheckOpenGLError();\n    for (size_t i = 0; i < mShipPointCount; ++i)\n    {\n        pDst[i].light = pSrc1[i];\n        pDst[i].water = pSrc2[i];\n        pDst[i].temperature = pSrc3[i];\n        pDst[i].rot = pSrc4[i].x;\n        pDst[i].rust = pSrc4[i].y;\n        pDst[i].algaeGrowth = pSrc4[i].z;\n    }\n\n    glUnmapBuffer(GL_ARRAY_BUFFER);\n    CheckOpenGLError();''',
    '''    mPointAttributeGroupCpuBuffer.resize(mShipPointCount);\n    PointAttributeGroupVertex * const restrict pDst = mPointAttributeGroupCpuBuffer.data();\n    for (size_t i = 0; i < mShipPointCount; ++i)\n    {\n        pDst[i].light = pSrc1[i];\n        pDst[i].water = pSrc2[i];\n        pDst[i].temperature = pSrc3[i];\n        pDst[i].rot = pSrc4[i].x;\n        pDst[i].rust = pSrc4[i].y;\n        pDst[i].algaeGrowth = pSrc4[i].z;\n    }\n    glBufferSubData(GL_ARRAY_BUFFER, 0, mPointAttributeGroupCpuBuffer.size() * sizeof(PointAttributeGroupVertex), mPointAttributeGroupCpuBuffer.data());\n    CheckOpenGLError();''',
)
replace_once(
    render_cpp,
    '''        // Map vertex buffer\n        auto mappedBuffer = reinterpret_cast<uint8_t *>(glMapBuffer(GL_ARRAY_BUFFER, GL_WRITE_ONLY));\n        CheckOpenGLError();\n\n        // Upload air bubbles\n        if (!mGenericMipMappedTextureAirBubbleVertexBuffer.empty())\n        {\n            size_t const byteCopySize = mGenericMipMappedTextureAirBubbleVertexBuffer.size() * sizeof(GenericTextureVertex);\n            std::memcpy(mappedBuffer, mGenericMipMappedTextureAirBubbleVertexBuffer.data(), byteCopySize);\n            mappedBuffer += byteCopySize;\n        }\n\n        // Upload all planes of other textures\n        for (auto const & plane : mGenericMipMappedTexturePlaneQuadBuffers)\n        {\n            if (!plane.quadBuffer.empty())\n            {\n                size_t const byteCopySize = plane.quadBuffer.size() * sizeof(GenericTextureQuad);\n                std::memcpy(mappedBuffer, plane.quadBuffer.data(), byteCopySize);\n                mappedBuffer += byteCopySize;\n            }\n        }\n\n        // Unmap vertex buffer\n        glUnmapBuffer(GL_ARRAY_BUFFER);\n        CheckOpenGLError();''',
    '''        mGenericMipMappedTextureCpuBuffer.resize(mGenericMipMappedTextureTotalVertexCount * sizeof(GenericTextureVertex));\n        uint8_t * mappedBuffer = mGenericMipMappedTextureCpuBuffer.data();\n\n        // Upload air bubbles\n        if (!mGenericMipMappedTextureAirBubbleVertexBuffer.empty())\n        {\n            size_t const byteCopySize = mGenericMipMappedTextureAirBubbleVertexBuffer.size() * sizeof(GenericTextureVertex);\n            std::memcpy(mappedBuffer, mGenericMipMappedTextureAirBubbleVertexBuffer.data(), byteCopySize);\n            mappedBuffer += byteCopySize;\n        }\n\n        // Upload all planes of other textures\n        for (auto const & plane : mGenericMipMappedTexturePlaneQuadBuffers)\n        {\n            if (!plane.quadBuffer.empty())\n            {\n                size_t const byteCopySize = plane.quadBuffer.size() * sizeof(GenericTextureQuad);\n                std::memcpy(mappedBuffer, plane.quadBuffer.data(), byteCopySize);\n                mappedBuffer += byteCopySize;\n            }\n        }\n\n        glBufferSubData(\n            GL_ARRAY_BUFFER,\n            0,\n            mGenericMipMappedTextureCpuBuffer.size(),\n            mGenericMipMappedTextureCpuBuffer.data());\n        CheckOpenGLError();''',
)
replace_once(
    render_cpp,
    '''        // Map vertex buffer\n        auto mappedBuffer = reinterpret_cast<uint8_t *>(glMapBuffer(GL_ARRAY_BUFFER, GL_WRITE_ONLY));\n        CheckOpenGLError();\n\n        // Upload all planes\n        for (auto const & plane : mExplosionPlaneVertexBuffers)\n        {\n            if (!plane.vertexBuffer.empty())\n            {\n                size_t const byteCopySize = plane.vertexBuffer.size() * sizeof(ExplosionVertex);\n                std::memcpy(mappedBuffer, plane.vertexBuffer.data(), byteCopySize);\n                mappedBuffer += byteCopySize;\n            }\n        }\n\n        // Unmap vertex buffer\n        glUnmapBuffer(GL_ARRAY_BUFFER);''',
    '''        mExplosionCpuBuffer.resize(mExplosionTotalVertexCount * sizeof(ExplosionVertex));\n        uint8_t * mappedBuffer = mExplosionCpuBuffer.data();\n\n        // Upload all planes\n        for (auto const & plane : mExplosionPlaneVertexBuffers)\n        {\n            if (!plane.vertexBuffer.empty())\n            {\n                size_t const byteCopySize = plane.vertexBuffer.size() * sizeof(ExplosionVertex);\n                std::memcpy(mappedBuffer, plane.vertexBuffer.data(), byteCopySize);\n                mappedBuffer += byteCopySize;\n            }\n        }\n\n        glBufferSubData(\n            GL_ARRAY_BUFFER,\n            0,\n            mExplosionCpuBuffer.size(),\n            mExplosionCpuBuffer.data());\n        CheckOpenGLError();''',
)

remaining_maps = render_cpp.read_text(encoding="utf-8").count("glMapBuffer(")
if remaining_maps != 0:
    raise RuntimeError(f"ShipRenderContext still contains {remaining_maps} glMapBuffer calls")

# ---------------------------------------------------------------------------
# CMake-level Emscripten link/compile flags.  The workflow already supplies
# WebGL2, exception, memory-growth and audio flags; add the GLES3 bridge,
# browser-style runtime lifetime, exported runtime helpers, and WASM SIMD in
# the actual Floating Sandbox CMake project so they reach the final target.
# ---------------------------------------------------------------------------
fs_cmake = FS_ROOT / "CMakeLists.txt"
text = fs_cmake.read_text(encoding="utf-8")
flag_block = '''\n# Emscripten/WebGL2 target flags are added here so they reach both compile and\n# final link commands without requiring another workflow-edit commit.\nif(EMSCRIPTEN)\n    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -sFULL_ES3=1 -sEXIT_RUNTIME=0 -msimd128")\n    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -sFULL_ES3=1 -sEXIT_RUNTIME=0 -sEXPORTED_RUNTIME_METHODS=ccall,cwrap -msimd128")\nendif()\n'''
if "sFULL_ES3=1" not in text:
    marker = "project (FloatingSandbox)\n"
    if marker not in text:
        raise RuntimeError("Could not locate Floating Sandbox project() declaration")
    fs_cmake.write_text(text.replace(marker, marker + flag_block, 1), encoding="utf-8")

# Verify all critical patches landed in the files that the build will compile.
checks = [
    (shader_manager, "#version 300 es"),
    (shader_manager, "precision highp float;"),
    (FS_ROOT / "Sources/OpenGLCore/GameOpenGL.cpp", "#ifndef __EMSCRIPTEN__"),
    (ext, "glDrawArraysInstanced"),
    (render_cpp, "glBufferSubData(GL_ARRAY_BUFFER"),
    (fs_cmake, "sFULL_ES3=1"),
]
for path, needle in checks:
    if needle not in path.read_text(encoding="utf-8"):
        raise RuntimeError(f"Critical Emscripten/WebGL2 patch missing from {path}: {needle}")

print("WASM compatibility + WebGL2 render preparation completed successfully")

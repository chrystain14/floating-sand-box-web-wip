from pathlib import Path
import os

FS_ROOT = Path("upstream-floating-sandbox")
SFML_ROOT = Path("sfml-src")
SYSROOT = Path(os.environ["EM_SYSROOT"])


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text was not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# SFML 2.5.1: make its platform detection understand Emscripten without
# pretending that Emscripten is Linux. The latter would add Linux-only rt/dl.
# ---------------------------------------------------------------------------
config = SFML_ROOT / "cmake/Config.cmake"
replace_once(
    config,
    'elseif(${CMAKE_SYSTEM_NAME} STREQUAL "Darwin")',
    '''elseif(${CMAKE_SYSTEM_NAME} STREQUAL "Emscripten")
    set(SFML_OS_UNIX 1)
    set(SFML_OS_EMSCRIPTEN 1)
    set(OPENGL_ES 1)
elseif(${CMAKE_SYSTEM_NAME} STREQUAL "Darwin")''',
)

modules = SFML_ROOT / "cmake/Modules"
modules.mkdir(parents=True, exist_ok=True)

(modules / "FindOpenAL.cmake").write_text(
    f'''set(OPENAL_FOUND TRUE)
set(OpenAL_FOUND TRUE)
set(OPENAL_INCLUDE_DIR "{SYSROOT / 'include'}")
set(OPENAL_LIBRARY "-lopenal")
''',
    encoding="utf-8",
)

(modules / "FindVorbis.cmake").write_text(
    f'''set(VORBIS_FOUND TRUE)
set(Vorbis_FOUND TRUE)
set(VORBIS_INCLUDE_DIRS "{SYSROOT / 'include'}")
set(VORBIS_LIBRARIES "-lvorbisfile;-lvorbis;-logg")
''',
    encoding="utf-8",
)

# SFML's FLAC implementation needs a native libFLAC dependency. The browser
# build keeps WAV + OGG support and removes only the FLAC reader/writer.
audio_cmake = SFML_ROOT / "src/SFML/Audio/CMakeLists.txt"
replace_once(
    audio_cmake,
    '''set(CODECS_SRC
    ${SRCROOT}/SoundFileFactory.cpp
    ${INCROOT}/SoundFileFactory.hpp
    ${INCROOT}/SoundFileFactory.inl
    ${INCROOT}/SoundFileReader.hpp
    ${SRCROOT}/SoundFileReaderFlac.hpp
    ${SRCROOT}/SoundFileReaderFlac.cpp
    ${SRCROOT}/SoundFileReaderOgg.hpp
    ${SRCROOT}/SoundFileReaderOgg.cpp
    ${SRCROOT}/SoundFileReaderWav.hpp
    ${SRCROOT}/SoundFileReaderWav.cpp
    ${INCROOT}/SoundFileWriter.hpp
    ${SRCROOT}/SoundFileWriterFlac.hpp
    ${SRCROOT}/SoundFileWriterFlac.cpp
    ${SRCROOT}/SoundFileWriterOgg.hpp
    ${SRCROOT}/SoundFileWriterOgg.cpp
    ${SRCROOT}/SoundFileWriterWav.hpp
    ${SRCROOT}/SoundFileWriterWav.cpp
)''',
    '''if(SFML_OS_EMSCRIPTEN)
    set(CODECS_SRC
        ${SRCROOT}/SoundFileFactory.cpp
        ${INCROOT}/SoundFileFactory.hpp
        ${INCROOT}/SoundFileFactory.inl
        ${INCROOT}/SoundFileReader.hpp
        ${SRCROOT}/SoundFileReaderOgg.hpp
        ${SRCROOT}/SoundFileReaderOgg.cpp
        ${SRCROOT}/SoundFileReaderWav.hpp
        ${SRCROOT}/SoundFileReaderWav.cpp
        ${INCROOT}/SoundFileWriter.hpp
        ${SRCROOT}/SoundFileWriterOgg.hpp
        ${SRCROOT}/SoundFileWriterOgg.cpp
        ${SRCROOT}/SoundFileWriterWav.hpp
        ${SRCROOT}/SoundFileWriterWav.cpp
    )
else()
    set(CODECS_SRC
        ${SRCROOT}/SoundFileFactory.cpp
        ${INCROOT}/SoundFileFactory.hpp
        ${INCROOT}/SoundFileFactory.inl
        ${INCROOT}/SoundFileReader.hpp
        ${SRCROOT}/SoundFileReaderFlac.hpp
        ${SRCROOT}/SoundFileReaderFlac.cpp
        ${SRCROOT}/SoundFileReaderOgg.hpp
        ${SRCROOT}/SoundFileReaderOgg.cpp
        ${SRCROOT}/SoundFileReaderWav.hpp
        ${SRCROOT}/SoundFileReaderWav.cpp
        ${INCROOT}/SoundFileWriter.hpp
        ${SRCROOT}/SoundFileWriterFlac.hpp
        ${SRCROOT}/SoundFileWriterFlac.cpp
        ${SRCROOT}/SoundFileWriterOgg.hpp
        ${SRCROOT}/SoundFileWriterOgg.cpp
        ${SRCROOT}/SoundFileWriterWav.hpp
        ${SRCROOT}/SoundFileWriterWav.cpp
    )
endif()''',
)

replace_once(
    audio_cmake,
    '''sfml_find_package(OpenAL INCLUDE "OPENAL_INCLUDE_DIR" LINK "OPENAL_LIBRARY")
sfml_find_package(Vorbis INCLUDE "VORBIS_INCLUDE_DIRS" LINK "VORBIS_LIBRARIES")
sfml_find_package(FLAC INCLUDE "FLAC_INCLUDE_DIR" LINK "FLAC_LIBRARY")''',
    '''sfml_find_package(OpenAL INCLUDE "OPENAL_INCLUDE_DIR" LINK "OPENAL_LIBRARY")
sfml_find_package(Vorbis INCLUDE "VORBIS_INCLUDE_DIRS" LINK "VORBIS_LIBRARIES")
if(NOT SFML_OS_EMSCRIPTEN)
    sfml_find_package(FLAC INCLUDE "FLAC_INCLUDE_DIR" LINK "FLAC_LIBRARY")
endif()''',
)

replace_once(
    audio_cmake,
    '''target_compile_definitions(Vorbis INTERFACE "OV_EXCLUDE_STATIC_CALLBACKS")
target_compile_definitions(FLAC INTERFACE "FLAC__NO_DLL")''',
    '''target_compile_definitions(Vorbis INTERFACE "OV_EXCLUDE_STATIC_CALLBACKS")
if(NOT SFML_OS_EMSCRIPTEN)
    target_compile_definitions(FLAC INTERFACE "FLAC__NO_DLL")
endif()''',
)

replace_once(
    audio_cmake,
    '''target_link_libraries(sfml-audio
                      PUBLIC sfml-system
                      PRIVATE Vorbis FLAC)''',
    '''if(SFML_OS_EMSCRIPTEN)
    target_link_libraries(sfml-audio PUBLIC sfml-system PRIVATE Vorbis)
else()
    target_link_libraries(sfml-audio PUBLIC sfml-system PRIVATE Vorbis FLAC)
endif()''',
)

factory = SFML_ROOT / "src/SFML/Audio/SoundFileFactory.cpp"
replace_once(
    factory,
    '#include <SFML/Audio/SoundFileReaderFlac.hpp>\n#include <SFML/Audio/SoundFileWriterFlac.hpp>\n',
    '#ifndef __EMSCRIPTEN__\n#include <SFML/Audio/SoundFileReaderFlac.hpp>\n#include <SFML/Audio/SoundFileWriterFlac.hpp>\n#endif\n',
)
replace_once(
    factory,
    '''            sf::SoundFileFactory::registerReader<sf::priv::SoundFileReaderFlac>();
            sf::SoundFileFactory::registerWriter<sf::priv::SoundFileWriterFlac>();
''',
    '''#ifndef __EMSCRIPTEN__
            sf::SoundFileFactory::registerReader<sf::priv::SoundFileReaderFlac>();
            sf::SoundFileFactory::registerWriter<sf::priv::SoundFileWriterFlac>();
#endif
''',
)

# ---------------------------------------------------------------------------
# Floating Sandbox OpenGL loader: Emscripten already owns the WebGL context;
# route GL symbol lookups through its WebGL implementation instead of dlopen.
# ---------------------------------------------------------------------------
glad = FS_ROOT / "Sources/OpenGLCore/glad/glad.c"
s = glad.read_text(encoding="utf-8")
marker = '#else\n#include <dlfcn.h>\nstatic void* libGL;'
if marker not in s:
    raise RuntimeError("Could not locate glad dynamic loader block")
start = s.index(marker)
end = s.index("struct gladGLversionStruct GLVersion", start)
replacement = r'''#else
#ifdef __EMSCRIPTEN__
#include <emscripten/html5_webgl.h>
static void* libGL;
int open_gl(void) { return 1; }
void close_gl(void) { libGL = NULL; }
void* get_proc(const char *namez) { return emscripten_webgl_get_proc_address(namez); }
#else
#include <dlfcn.h>
static void* libGL;
#if !defined(__APPLE__) && !defined(__HAIKU__)
typedef void* (APIENTRYP PFNGLXGETPROCADDRESSPROC_PRIVATE)(const char*);
static PFNGLXGETPROCADDRESSPROC_PRIVATE gladGetProcAddressPtr;
#endif
int open_gl(void) {
#ifdef __APPLE__
    static const char *NAMES[] = {
        "../Frameworks/OpenGL.framework/OpenGL",
        "/Library/Frameworks/OpenGL.framework/OpenGL",
        "/System/Library/Frameworks/OpenGL.framework/OpenGL",
        "/System/Library/Frameworks/OpenGL.framework/Versions/Current/OpenGL"
    };
#else
    static const char *NAMES[] = {"libGL.so.1", "libGL.so"};
#endif
    unsigned int index = 0;
    for(index = 0; index < (sizeof(NAMES) / sizeof(NAMES[0])); index++) {
        libGL = dlopen(NAMES[index], RTLD_NOW | RTLD_GLOBAL);
        if(libGL != NULL) {
#if defined(__APPLE__) || defined(__HAIKU__)
            return 1;
#else
            gladGetProcAddressPtr = (PFNGLXGETPROCADDRESSPROC_PRIVATE)dlsym(libGL, "glXGetProcAddressARB");
            return gladGetProcAddressPtr != NULL;
#endif
        }
    }
    return 0;
}
void close_gl(void) {
    if(libGL != NULL) {
        dlclose(libGL);
        libGL = NULL;
    }
}
void* get_proc(const char *namez) {
    void* result = NULL;
    if(libGL == NULL) return NULL;
#if !defined(__APPLE__) && !defined(__HAIKU__)
    if(gladGetProcAddressPtr != NULL) result = gladGetProcAddressPtr(namez);
#endif
    if(result == NULL) {
#if defined(_WIN32) || defined(__CYGWIN__)
        result = (void*)GetProcAddress((HMODULE) libGL, namez);
#else
        result = dlsym(libGL, namez);
#endif
    }
    return result;
}
#endif

'''
glad.write_text(s[:start] + replacement + s[end:], encoding="utf-8")

# Floating Sandbox asks CMake for OpenGL; under Emscripten we provide WebGL
# through the Emscripten toolchain, so there is no native libGL to discover.
(FS_ROOT / "cmake/FindOpenGL.cmake").write_text(
    '''include_guard()\nset(OpenGL_FOUND TRUE)\nset(OPENGL_FOUND TRUE)\nset(OPENGL_LIBRARIES "")\nset(OPENGL_INCLUDE_DIRS "")\nif(NOT TARGET OpenGL::GL)\n  add_library(OpenGL::GL INTERFACE IMPORTED)\nendif()\n''',
    encoding="utf-8",
)

# wx-config is valid for the cross-compiled toolkit, but Floating Sandbox's
# customized FindwxWidgets tries native find_library() checks that do not work
# with Emscripten's rooted sysroot. This shim trusts wx-config's cross flags.
(FS_ROOT / "cmake/FindwxWidgets.cmake").write_text(
    '''include(FindPackageHandleStandardArgs)\nif(NOT wxWidgets_CONFIG_EXECUTABLE)\n  if(DEFINED ENV{WX_CONFIG} AND EXISTS "$ENV{WX_CONFIG}")\n    set(wxWidgets_CONFIG_EXECUTABLE "$ENV{WX_CONFIG}")\n  else()\n    find_program(wxWidgets_CONFIG_EXECUTABLE NAMES wx-config wx-config-3.1)\n  endif()\nendif()\nset(wxWidgets_FOUND FALSE)\nset(wxWidgets_INCLUDE_DIRS "")\nset(wxWidgets_LIBRARIES "")\nset(wxWidgets_LIBRARY_DIRS "")\nset(wxWidgets_CXX_FLAGS "")\nset(wxWidgets_DEFINITIONS "")\nset(wxWidgets_USE_FILE "${CMAKE_CURRENT_LIST_DIR}/wxWidgetsUseFile.cmake")\nif(wxWidgets_CONFIG_EXECUTABLE)\n  execute_process(COMMAND "${wxWidgets_CONFIG_EXECUTABLE}" --cxxflags OUTPUT_VARIABLE _wx_cxxflags RESULT_VARIABLE _wx_cxx_ret OUTPUT_STRIP_TRAILING_WHITESPACE)\n  execute_process(COMMAND "${wxWidgets_CONFIG_EXECUTABLE}" --libs base,core,html,propgrid,ribbon OUTPUT_VARIABLE _wx_libs RESULT_VARIABLE _wx_lib_ret OUTPUT_STRIP_TRAILING_WHITESPACE)\n  message(STATUS "FindwxWidgets(WASM): cxxflags ret=${_wx_cxx_ret} out='${_wx_cxxflags}'")\n  message(STATUS "FindwxWidgets(WASM): libs ret=${_wx_lib_ret} out='${_wx_libs}'")\n  if(_wx_cxx_ret EQUAL 0 AND _wx_lib_ret EQUAL 0 AND NOT "${_wx_libs}" STREQUAL "")\n    separate_arguments(_wx_cxxflags NATIVE_COMMAND "${_wx_cxxflags}")\n    separate_arguments(_wx_lib_list NATIVE_COMMAND "${_wx_libs}")\n    foreach(_arg IN LISTS _wx_cxxflags)\n      if(_arg MATCHES "^-I(.+)$")\n        list(APPEND wxWidgets_INCLUDE_DIRS "${CMAKE_MATCH_1}")\n      elseif(_arg MATCHES "^-D(.+)$")\n        list(APPEND wxWidgets_DEFINITIONS "${CMAKE_MATCH_1}")\n      else()\n        list(APPEND wxWidgets_CXX_FLAGS "${_arg}")\n      endif()\n    endforeach()\n    foreach(_arg IN LISTS _wx_lib_list)\n      if(_arg MATCHES "^-L(.+)$")\n        list(APPEND wxWidgets_LIBRARY_DIRS "${CMAKE_MATCH_1}")\n      else()\n        list(APPEND wxWidgets_LIBRARIES "${_arg}")\n      endif()\n    endforeach()\n    set(wxWidgets_FOUND TRUE)\n  endif()\nendif()\nfind_package_handle_standard_args(wxWidgets REQUIRED_VARS wxWidgets_CONFIG_EXECUTABLE wxWidgets_INCLUDE_DIRS wxWidgets_LIBRARIES)\n''',
    encoding="utf-8",
)
(FS_ROOT / "cmake/wxWidgetsUseFile.cmake").write_text("# Emscripten wx-config flags are supplied through CXXFLAGS.\n", encoding="utf-8")

# FindSFML is deliberately a module rather than SFMLConfig.cmake so the main
# project does not re-run native dependency discovery for OpenAL/Vorbis/FLAC.
(FS_ROOT / "cmake/FindSFML.cmake").write_text(
    '''include(FindPackageHandleStandardArgs)\nif(NOT SFML_ROOT)\n  set(SFML_ROOT "$ENV{GITHUB_WORKSPACE}/sfml-install")\nendif()\nset(SFML_VERSION_STRING "2.5.1")\nset(SFML_VERSION_MAJOR 2)\nset(SFML_VERSION_MINOR 5)\nset(SFML_VERSION_PATCH 1)\nset(SFML_INCLUDE_DIR "${SFML_ROOT}/include")\nset(SFML_INCLUDE_DIRS "${SFML_ROOT}/include")\nset(SFML_FOUND TRUE)\nforeach(_sfml_name IN ITEMS sfml-system sfml-network sfml-audio)\n  if(NOT TARGET ${_sfml_name})\n    add_library(${_sfml_name} STATIC IMPORTED GLOBAL)\n    set_target_properties(${_sfml_name} PROPERTIES\n      IMPORTED_LOCATION "${SFML_ROOT}/lib/lib${_sfml_name}-s.a"\n      INTERFACE_INCLUDE_DIRECTORIES "${SFML_ROOT}/include")\n  endif()\nendforeach()\nset_target_properties(sfml-network PROPERTIES INTERFACE_LINK_LIBRARIES "sfml-system")\nset_target_properties(sfml-audio PROPERTIES INTERFACE_LINK_LIBRARIES "sfml-system;-lopenal;-lvorbisfile;-lvorbis;-logg")\nfind_package_handle_standard_args(SFML REQUIRED_VARS SFML_ROOT SFML_INCLUDE_DIRS VERSION_VAR SFML_VERSION_STRING)\n''',
    encoding="utf-8",
)

print("WASM compatibility preparation completed successfully")
print(f"Emscripten sysroot: {SYSROOT}")

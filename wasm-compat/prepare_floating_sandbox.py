from pathlib import Path

FS_ROOT = Path("upstream-floating-sandbox")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text was not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Floating Sandbox uses GLAD to load desktop OpenGL symbols dynamically.
# In Emscripten there is no desktop libGL, so use the active WebGL context.
glad = FS_ROOT / "Sources/OpenGLCore/glad/glad.c"
s = glad.read_text(encoding="utf-8")
marker = '#else\n#include <dlfcn.h>\nstatic void* libGL;'
if marker not in s:
    raise RuntimeError("Could not locate GLAD dynamic loader block")
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

# CMake should treat WebAssembly's WebGL implementation as OpenGL::GL.
(FS_ROOT / "cmake/FindOpenGL.cmake").write_text(
    '''include_guard()\nset(OpenGL_FOUND TRUE)\nset(OPENGL_FOUND TRUE)\nset(OPENGL_LIBRARIES "")\nset(OPENGL_INCLUDE_DIRS "")\nif(NOT TARGET OpenGL::GL)\n  add_library(OpenGL::GL INTERFACE IMPORTED)\nendif()\n''',
    encoding="utf-8",
)

# The wxWidgets port supplies a cross-compiled wx-config. Use its flags instead
# of native find_library checks that do not work against an Emscripten sysroot.
(FS_ROOT / "cmake/FindwxWidgets.cmake").write_text(
    '''include(FindPackageHandleStandardArgs)\nif(NOT wxWidgets_CONFIG_EXECUTABLE)\n  if(DEFINED ENV{WX_CONFIG} AND EXISTS "$ENV{WX_CONFIG}")\n    set(wxWidgets_CONFIG_EXECUTABLE "$ENV{WX_CONFIG}")\n  else()\n    find_program(wxWidgets_CONFIG_EXECUTABLE NAMES wx-config wx-config-3.1)\n  endif()\nendif()\nset(wxWidgets_FOUND FALSE)\nset(wxWidgets_INCLUDE_DIRS "")\nset(wxWidgets_LIBRARIES "")\nset(wxWidgets_LIBRARY_DIRS "")\nset(wxWidgets_CXX_FLAGS "")\nset(wxWidgets_DEFINITIONS "")\nset(wxWidgets_USE_FILE "${CMAKE_CURRENT_LIST_DIR}/wxWidgetsUseFile.cmake")\nif(wxWidgets_CONFIG_EXECUTABLE)\n  execute_process(COMMAND "${wxWidgets_CONFIG_EXECUTABLE}" --cxxflags OUTPUT_VARIABLE _wx_cxxflags RESULT_VARIABLE _wx_cxx_ret OUTPUT_STRIP_TRAILING_WHITESPACE)\n  execute_process(COMMAND "${wxWidgets_CONFIG_EXECUTABLE}" --libs base,core,html,propgrid,ribbon OUTPUT_VARIABLE _wx_libs RESULT_VARIABLE _wx_lib_ret OUTPUT_STRIP_TRAILING_WHITESPACE)\n  if(_wx_cxx_ret EQUAL 0 AND _wx_lib_ret EQUAL 0 AND NOT "${_wx_libs}" STREQUAL "")\n    separate_arguments(_wx_cxxflags NATIVE_COMMAND "${_wx_cxxflags}")\n    separate_arguments(_wx_lib_list NATIVE_COMMAND "${_wx_libs}")\n    foreach(_arg IN LISTS _wx_cxxflags)\n      if(_arg MATCHES "^-I(.+)$")\n        list(APPEND wxWidgets_INCLUDE_DIRS "${CMAKE_MATCH_1}")\n      elseif(_arg MATCHES "^-D(.+)$")\n        list(APPEND wxWidgets_DEFINITIONS "${CMAKE_MATCH_1}")\n      else()\n        list(APPEND wxWidgets_CXX_FLAGS "${_arg}")\n      endif()\n    endforeach()\n    foreach(_arg IN LISTS _wx_lib_list)\n      if(_arg MATCHES "^-L(.+)$")\n        list(APPEND wxWidgets_LIBRARY_DIRS "${CMAKE_MATCH_1}")\n      else()\n        list(APPEND wxWidgets_LIBRARIES "${_arg}")\n      endif()\n    endforeach()\n    set(wxWidgets_FOUND TRUE)\n  endif()\nendif()\nfind_package_handle_standard_args(wxWidgets REQUIRED_VARS wxWidgets_CONFIG_EXECUTABLE wxWidgets_INCLUDE_DIRS wxWidgets_LIBRARIES)\n''',
    encoding="utf-8",
)
(FS_ROOT / "cmake/wxWidgetsUseFile.cmake").write_text(
    "# Emscripten wx-config flags are supplied through CXXFLAGS.\n",
    encoding="utf-8",
)

# The project ships a native-only SFML finder. For WebAssembly, bind directly
# to the static SFML libraries we just built and avoid desktop dependency scans.
(FS_ROOT / "cmake/FindSFML.cmake").write_text(
    '''include_guard()\n\nset(_SFML_ROOT "${SFML_ROOT}")\nif(NOT _SFML_ROOT)\n  if(DEFINED ENV{SFML_ROOT})\n    set(_SFML_ROOT "$ENV{SFML_ROOT}")\n  endif()\nendif()\n\nif(NOT _SFML_ROOT)\n  set(SFML_FOUND FALSE)\n  if(SFML_FIND_REQUIRED)\n    message(FATAL_ERROR "SFML_ROOT is required for the WebAssembly SFML build")\n  endif()\n  return()\nendif()\n\nset(SFML_INCLUDE_DIR "${_SFML_ROOT}/include")\nset(SFML_INCLUDE_DIRS "${SFML_INCLUDE_DIR}")\nset(SFML_LIBRARY_DIR "${_SFML_ROOT}/lib")\n\nfind_path(SFML_INCLUDE_DIR SFML/Config.hpp PATHS "${_SFML_ROOT}/include" NO_DEFAULT_PATH)\n\nforeach(_component IN LISTS SFML_FIND_COMPONENTS)\n  find_library(SFML_${_component}_LIBRARY\n    NAMES "sfml-${_component}-s" "sfml-${_component}"\n    PATHS "${_SFML_ROOT}/lib"\n    NO_DEFAULT_PATH)\n  if(NOT SFML_${_component}_LIBRARY)\n    set(SFML_FOUND FALSE)\n    if(SFML_FIND_REQUIRED)\n      message(FATAL_ERROR "Could not find SFML component '${_component}' under ${_SFML_ROOT}/lib")\n    endif()\n    return()\n  endif()\nendforeach()\n\nset(SFML_FOUND TRUE)\nset(SFML_VERSION_MAJOR 2)\nset(SFML_VERSION_MINOR 6)\nset(SFML_VERSION_PATCH 0)\nset(SFML_VERSION "2.6.0")\n\nforeach(_component IN LISTS SFML_FIND_COMPONENTS)\n  if(NOT TARGET sfml-${_component})\n    add_library(sfml-${_component} STATIC IMPORTED GLOBAL)\n    set_target_properties(sfml-${_component} PROPERTIES\n      IMPORTED_LOCATION "${SFML_${_component}_LIBRARY}"\n      INTERFACE_INCLUDE_DIRECTORIES "${SFML_INCLUDE_DIR}")\n  endif()\nendforeach()\n\nif(TARGET sfml-network AND TARGET sfml-system)\n  set_property(TARGET sfml-network APPEND PROPERTY INTERFACE_LINK_LIBRARIES sfml-system)\nendif()\nif(TARGET sfml-audio AND TARGET sfml-system)\n  set_property(TARGET sfml-audio APPEND PROPERTY INTERFACE_LINK_LIBRARIES\n    sfml-system -lopenal -lvorbisfile -lvorbis -logg)\nendif()\n\nforeach(_component IN LISTS SFML_FIND_COMPONENTS)\n  string(TOUPPER "${_component}" _upper)\n  set(SFML_${_upper}_FOUND TRUE)\nendforeach()\n\nmessage(STATUS "Found WebAssembly SFML 2.6.0 in ${_SFML_ROOT}")\n''',
    encoding="utf-8",
)

# Floating Sandbox's desktop GNU branch adds X11/desktop runtime libraries.
# Remove that path for Emscripten and keep only libraries usable in WebAssembly.
root_cmake = FS_ROOT / "CMakeLists.txt"
root_text = root_cmake.read_text(encoding="utf-8")
old = '''elseif("${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU")\n\tset(ADDITIONAL_LIBRARIES ${CMAKE_DL_LIBS} pthread stdc++fs atomic png jpeg)\n\tif (UNIX)\n\t    list(APPEND ADDITIONAL_LIBRARIES X11)\n\tendif (UNIX)\nendif()'''
new = '''elseif("${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU")\n\tif(EMSCRIPTEN)\n\t\tset(ADDITIONAL_LIBRARIES pthread png jpeg)\n\telse()\n\t\tset(ADDITIONAL_LIBRARIES ${CMAKE_DL_LIBS} pthread stdc++fs atomic png jpeg)\n\t\tif (UNIX)\n\t\t    list(APPEND ADDITIONAL_LIBRARIES X11)\n\t\tendif (UNIX)\n\tendif()\nendif()'''
if old not in root_text:
    raise RuntimeError("Could not locate GNU ADDITIONAL_LIBRARIES block")
root_cmake.write_text(root_text.replace(old, new, 1), encoding="utf-8")

print("Floating Sandbox WebAssembly preparation completed")

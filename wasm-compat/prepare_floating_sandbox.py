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

print("Floating Sandbox WebAssembly preparation completed")

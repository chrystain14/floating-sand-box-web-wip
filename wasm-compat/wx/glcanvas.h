#pragma once

#include <wx/panel.h>

#ifdef __EMSCRIPTEN__

#include <emscripten/html5_webgl.h>
#include <emscripten/threading.h>

#include <atomic>
#include <string>

namespace floating_sandbox_wasm_gl
{
inline std::atomic<unsigned> gNextCanvasId{0};

inline std::string MakeSelector()
{
    return std::string("#fs-wasm-glcanvas-") + std::to_string(gNextCanvasId.fetch_add(1));
}

EM_JS(void, CreateCanvasElement, (const char * selector),
{
    const id = UTF8ToString(selector).substring(1);
    if (document.getElementById(id)) return;

    const canvas = document.createElement('canvas');
    canvas.id = id;
    canvas.style.position = 'fixed';
    canvas.style.margin = '0';
    canvas.style.padding = '0';
    canvas.style.border = '0';
    canvas.style.pointerEvents = 'none';
    canvas.style.display = 'block';
    canvas.style.zIndex = '5';
    document.body.appendChild(canvas);
});

EM_JS(void, DestroyCanvasElement, (const char * selector),
{
    const canvas = document.querySelector(UTF8ToString(selector));
    if (canvas) canvas.remove();
});

EM_JS(void, SyncCanvasElement, (const char * selector, int x, int y, int width, int height),
{
    const canvas = document.querySelector(UTF8ToString(selector));
    if (!canvas) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.style.left = `${x}px`;
    canvas.style.top = `${y}px`;
    canvas.style.width = `${Math.max(1, width)}px`;
    canvas.style.height = `${Math.max(1, height)}px`;

    const pixelWidth = Math.max(1, Math.round(width * dpr));
    const pixelHeight = Math.max(1, Math.round(height * dpr));
    if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
    if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
});
}

class wxGLAttributes
{
public:
    wxGLAttributes & PlatformDefaults() { return *this; }
    wxGLAttributes & RGBA() { return *this; }
    wxGLAttributes & DoubleBuffer() { return *this; }
    wxGLAttributes & Depth(int) { return *this; }
    wxGLAttributes & SampleBuffers(int) { return *this; }
    wxGLAttributes & Samplers(int) { return *this; }
    void EndList() {}
};

class wxGLCanvas;

class wxGLContext
{
public:
    explicit wxGLContext(wxGLCanvas * canvas);
    ~wxGLContext();

    bool SetCurrent(wxGLCanvas & canvas) const;

private:
    EMSCRIPTEN_WEBGL_CONTEXT_HANDLE mContext;

    friend class wxGLCanvas;
};

class wxGLCanvas : public wxPanel
{
public:
    static bool IsDisplaySupported(wxGLAttributes const &)
    {
        return true;
    }

    wxGLCanvas(
        wxWindow * parent,
        wxGLAttributes const &,
        wxWindowID id,
        wxPoint const & pos = wxDefaultPosition,
        wxSize const & size = wxDefaultSize,
        long style = 0L)
        : wxPanel(parent, id, pos, size, style)
        , mCanvasSelector(floating_sandbox_wasm_gl::MakeSelector())
        , mContext(0)
    {
        floating_sandbox_wasm_gl::CreateCanvasElement(mCanvasSelector.c_str());

        EmscriptenWebGLContextAttributes attrs;
        emscripten_webgl_init_context_attributes(&attrs);
        attrs.alpha = EM_FALSE;
        attrs.depth = EM_TRUE;
        attrs.stencil = EM_FALSE;
        attrs.antialias = EM_TRUE;
        attrs.premultipliedAlpha = EM_FALSE;
        attrs.preserveDrawingBuffer = EM_FALSE;
        attrs.enableExtensionsByDefault = EM_TRUE;
        attrs.majorVersion = 2;
        attrs.minorVersion = 0;

        mContext = emscripten_webgl_create_context(mCanvasSelector.c_str(), &attrs);
        if (mContext > 0)
            emscripten_webgl_make_context_current(mContext);

        SyncCanvas();
    }

    wxGLCanvas(
        wxWindow * parent,
        wxWindowID id,
        wxGLAttributes const & attributes,
        wxPoint const & pos = wxDefaultPosition,
        wxSize const & size = wxDefaultSize,
        long style = 0L)
        : wxGLCanvas(parent, attributes, id, pos, size, style)
    {
    }

    ~wxGLCanvas() override
    {
        if (mContext > 0)
        {
            emscripten_webgl_destroy_context(mContext);
            mContext = 0;
        }

        floating_sandbox_wasm_gl::DestroyCanvasElement(mCanvasSelector.c_str());
    }

    bool SetCurrent()
    {
        return SetCurrentContext(mContext);
    }

    void SwapBuffers()
    {
        SyncCanvas();
        if (mContext > 0)
            emscripten_webgl_make_context_current(mContext);
    }

    EMSCRIPTEN_WEBGL_CONTEXT_HANDLE GetWasmContext() const
    {
        return mContext;
    }

private:
    bool SetCurrentContext(EMSCRIPTEN_WEBGL_CONTEXT_HANDLE context)
    {
        if (context <= 0)
            return false;

        SyncCanvas();
        return emscripten_webgl_make_context_current(context) == EMSCRIPTEN_RESULT_SUCCESS;
    }

    void SyncCanvas()
    {
        wxPoint const screenPos = GetScreenPosition();
        wxSize const size = GetSize();
        floating_sandbox_wasm_gl::SyncCanvasElement(
            mCanvasSelector.c_str(),
            screenPos.x,
            screenPos.y,
            size.GetWidth(),
            size.GetHeight());
    }

private:
    std::string mCanvasSelector;
    EMSCRIPTEN_WEBGL_CONTEXT_HANDLE mContext;

    friend class wxGLContext;
};

inline wxGLContext::wxGLContext(wxGLCanvas * canvas)
    : mContext(canvas != nullptr ? canvas->GetWasmContext() : 0)
{
}

inline wxGLContext::~wxGLContext() = default;

inline bool wxGLContext::SetCurrent(wxGLCanvas & canvas) const
{
    EMSCRIPTEN_WEBGL_CONTEXT_HANDLE context = mContext > 0 ? mContext : canvas.GetWasmContext();
    if (context <= 0)
        return false;

    wxPoint const screenPos = canvas.GetScreenPosition();
    wxSize const size = canvas.GetSize();
    floating_sandbox_wasm_gl::SyncCanvasElement(
        "",
        screenPos.x,
        screenPos.y,
        size.GetWidth(),
        size.GetHeight());

    return emscripten_webgl_make_context_current(context) == EMSCRIPTEN_RESULT_SUCCESS;
}

#else

#error "wasm-compat/wx/glcanvas.h is only intended for Emscripten builds"

#endif

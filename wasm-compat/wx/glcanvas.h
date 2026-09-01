#pragma once

#include <wx/panel.h>

#ifdef __EMSCRIPTEN__

#include <emscripten/html5_webgl.h>

#include <atomic>
#include <string>

namespace floating_sandbox_wasm_gl
{
inline std::atomic<unsigned> gNextCanvasId{0};

inline std::string MakeSelector()
{
    return std::string("#fs-wasm-glcanvas-") + std::to_string(gNextCanvasId.fetch_add(1));
}
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
    ~wxGLContext() = default;

    bool SetCurrent(wxGLCanvas & canvas) const;

private:
    EMSCRIPTEN_WEBGL_CONTEXT_HANDLE mContext;
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
        EM_ASM({
            const selector = UTF8ToString($0);
            const id = selector.substring(1);
            if (!document.getElementById(id)) {
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
            }
        }, mCanvasSelector.c_str());

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

        EM_ASM({
            const selector = UTF8ToString($0);
            const canvas = document.querySelector(selector);
            if (canvas) canvas.remove();
        }, mCanvasSelector.c_str());
    }

    bool SetCurrent()
    {
        if (mContext <= 0)
            return false;

        SyncCanvas();
        return emscripten_webgl_make_context_current(mContext) == EMSCRIPTEN_RESULT_SUCCESS;
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

    char const * GetWasmCanvasSelector() const
    {
        return mCanvasSelector.c_str();
    }

private:
    void SyncCanvas() const
    {
        wxPoint const screenPos = GetScreenPosition();
        wxSize const size = GetSize();
        const int x = screenPos.x;
        const int y = screenPos.y;
        const int width = size.GetWidth();
        const int height = size.GetHeight();

        EM_ASM({
            const selector = UTF8ToString($0);
            const canvas = document.querySelector(selector);
            if (!canvas) return;

            const dpr = window.devicePixelRatio || 1;
            const x = $1;
            const y = $2;
            const width = Math.max(1, $3);
            const height = Math.max(1, $4);

            canvas.style.left = `${x}px`;
            canvas.style.top = `${y}px`;
            canvas.style.width = `${width}px`;
            canvas.style.height = `${height}px`;

            const pixelWidth = Math.max(1, Math.round(width * dpr));
            const pixelHeight = Math.max(1, Math.round(height * dpr));
            if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
            if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
        }, mCanvasSelector.c_str(), x, y, width, height);
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

inline bool wxGLContext::SetCurrent(wxGLCanvas & canvas) const
{
    EMSCRIPTEN_WEBGL_CONTEXT_HANDLE context = mContext > 0 ? mContext : canvas.GetWasmContext();
    if (context <= 0)
        return false;

    return canvas.SetCurrent();
}

#else

#error "wasm-compat/wx/glcanvas.h is only intended for Emscripten builds"

#endif

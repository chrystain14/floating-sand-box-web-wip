const MIME_TYPES = {
  ".html": "text/html; charset=UTF-8",
  ".js": "application/javascript; charset=UTF-8",
  ".mjs": "application/javascript; charset=UTF-8",
  ".wasm": "application/wasm",
  ".css": "text/css; charset=UTF-8",
  ".json": "application/json; charset=UTF-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".wav": "audio/wav",
  ".mp3": "audio/mpeg",
  ".ogg": "audio/ogg",
  ".mp4": "video/mp4",
  ".data": "application/octet-stream",
};

function getMime(pathname) {
  const dot = pathname.lastIndexOf(".");
  if (dot === -1) return null;
  return MIME_TYPES[pathname.slice(dot).toLowerCase()] || null;
}

function withHeaders(response, pathname) {
  const headers = new Headers(response.headers);
  const mime = getMime(pathname);
  if (mime) headers.set("Content-Type", mime);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Referrer-Policy", "same-origin");

  if (/\.(wasm|js|mjs|data)$/i.test(pathname)) {
    headers.set("Cache-Control", "public, max-age=31536000, immutable");
  } else if (/\.html$/i.test(pathname) || pathname.endsWith("/")) {
    headers.set("Cache-Control", "no-cache");
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function serveAsset(request, env, pathname) {
  if (!env?.ASSETS || typeof env.ASSETS.fetch !== "function") {
    return null;
  }

  const assetUrl = new URL(request.url);
  assetUrl.pathname = pathname;
  assetUrl.search = "";

  const response = await env.ASSETS.fetch(
    new Request(assetUrl, {
      method: request.method,
      headers: request.headers,
      redirect: "manual",
    })
  );

  if (response.status === 404) return null;
  return withHeaders(response, pathname);
}

function missingPage(pathname, reason = "Asset not found") {
  return new Response(`<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Floating Sandbox</title>
<style>
html,body{margin:0;width:100%;height:100%;background:#05080d;color:#fff;font-family:Arial,sans-serif}
main{height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}
code{background:#111722;padding:4px 7px;border-radius:6px}
</style>
</head>
<body><main>
<h1>🚢 Floating Sandbox Web</h1>
<p>${reason}</p>
<p><code>${pathname}</code></p>
</main></body></html>`, {
    status: 404,
    headers: {
      "Content-Type": "text/html; charset=UTF-8",
      "Cache-Control": "no-store",
    },
  });
}

export default {
  async fetch(request, env) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed", {
        status: 405,
        headers: { Allow: "GET, HEAD" },
      });
    }

    const url = new URL(request.url);
    let pathname = decodeURI(url.pathname);

    if (pathname === "/" || pathname === "/index.html" || pathname === "/floating-sandbox") {
      pathname = "/floating-sandbox/index.html";
    } else if (pathname.endsWith("/")) {
      pathname += "index.html";
    }

    const asset = await serveAsset(request, env, pathname);
    if (asset) return asset;

    if (!env?.ASSETS) {
      return missingPage(pathname, "Worker is running, but the ASSETS binding is unavailable");
    }

    return missingPage(pathname);
  },
};

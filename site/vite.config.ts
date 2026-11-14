/// <reference types="vitest/config" />
import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/**
 * What a static host needs beside the page itself. Every page of the site lives after the hash sign of one
 * address, so no address needs a rule on the server; an address that does not exist gets 404.html, a small
 * page of its own that leads back to the start. The link-preview tags get the address of the preview
 * picture: an absolute one when LUX_SITE_URL names where the site is published, as previews require.
 */
function staticHosting(base: string, siteUrl: string | undefined): Plugin {
  const home = base.startsWith("/") ? base : "./";
  const picture = siteUrl ? `${siteUrl.replace(/\/$/, "")}/og.jpg` : "og.jpg";
  return {
    name: "lux-static-hosting",
    transformIndexHtml: () => [
      { tag: "meta", attrs: { property: "og:image", content: picture }, injectTo: "head" },
      ...(siteUrl
        ? [
            {
              tag: "meta",
              attrs: { property: "og:url", content: `${siteUrl.replace(/\/$/, "")}/` },
              injectTo: "head" as const,
            },
            {
              tag: "link",
              attrs: { rel: "canonical", href: `${siteUrl.replace(/\/$/, "")}/` },
              injectTo: "head" as const,
            },
          ]
        : []),
    ],
    generateBundle() {
      this.emitFile({
        type: "asset",
        fileName: "404.html",
        source: `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="dark" />
    <title>Lux: no such page</title>
    <style>
      html { background: #000; color: #f4f2ec; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
      body { margin: 0; min-height: 100vh; display: grid; place-content: center; gap: 12px; padding: 24px; text-align: center; }
      h1 { margin: 0; font-size: 34px; letter-spacing: -0.03em; }
      p { margin: 0; color: #c9c7c1; }
      a { color: #ffc56b; font-weight: 650; text-underline-offset: 5px; }
    </style>
  </head>
  <body>
    <h1>There is no page at this address.</h1>
    <p><a href="${home}">Go to the start of Lux</a></p>
  </body>
</html>
`,
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  // LUX_BASE: the folder the site is served from, such as /lux/. Without it asset paths are relative, so the
  // built site works under any folder. LUX_SITE_URL: the full public address, for the link-preview tags.
  const env = loadEnv(mode, ".", "LUX_");
  const base = env.LUX_BASE || "./";
  return {
    plugins: [react(), staticHosting(base, env.LUX_SITE_URL)],
    base,
    // The words of the site live one folder up, in content/, beside the recordings they quote.
    server: { host: "127.0.0.1", port: 5183, strictPort: true, fs: { allow: [".."] } },
    preview: { host: "127.0.0.1", port: 5183, strictPort: true },
    // Load the real stylesheets in tests (the test runner stubs CSS by default), so the stylesheet guards read
    // actual rules.
    test: { css: { include: [/lux\.css/, /pages\.css/] } },
  };
});

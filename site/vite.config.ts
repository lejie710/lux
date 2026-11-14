/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Relative asset paths: the built site works under any folder.
  base: "./",
  // The words of the site live one folder up, in content/, beside the recordings they quote.
  server: { host: "127.0.0.1", port: 5183, strictPort: true, fs: { allow: [".."] } },
  preview: { host: "127.0.0.1", port: 5183, strictPort: true },
  // Load the real stylesheet in tests (the test runner stubs CSS by default), so the stylesheet guards read actual rules.
  test: { css: { include: [/lux\.css/] } },
});

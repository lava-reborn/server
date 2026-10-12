import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The page is served by tools/location_editor.py from static/; the API, the
// art cache and the objects' pictures are the same origin, so the dev
// server proxies them there. Every URL in the build is relative (base
// "./"), as the quest editor's, so the page can move under a prefix later.
const editor = "http://127.0.0.1:8096";
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "static", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 1200 },
  server: { proxy: { "/api": editor, "/art": editor } },
});

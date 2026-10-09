import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The page is served by tools/quest_editor.py from static/; the API is the
// same origin, so the dev server proxies it there.
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: { outDir: "static", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 1200 },
  server: { proxy: { "/api": "http://127.0.0.1:8095", "/icon": "http://127.0.0.1:8095" } },
});

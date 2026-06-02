import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/*
  In dev (`pnpm dev`) Vite serves the SPA on :5173 and proxies /api to the
  FastAPI backend on :8000. In prod, `pnpm build` emits to ./dist, which the
  backend serves directly — so there's no proxy and everything is one origin.
*/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});

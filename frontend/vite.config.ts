/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = process.env.VITE_DEV_BACKEND ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": backend, "/health": backend },
  },
  build: { sourcemap: false, chunkSizeWarningLimit: 600 },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});

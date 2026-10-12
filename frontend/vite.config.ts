/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // API_PORT lets e2e run its own backend next to a dev server on :8000
  server: { port: 5173, proxy: { "/api": `http://127.0.0.1:${process.env.API_PORT ?? 8000}` } },
  test: { environment: "jsdom", setupFiles: ["src/test/setup.ts"], css: false, include: ["src/**/*.test.{ts,tsx}"] },
});

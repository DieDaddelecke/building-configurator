/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Entwicklung: API und Web-Container laufen per docker compose; /api geht an die API (EMPRISE_API_URL überschreibt)
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: Number(process.env.PORT ?? 5173),
    proxy: {
      "/api": { target: process.env.EMPRISE_API_URL ?? "http://localhost:8000", xfwd: true },
    },
  },
  build: {
    sourcemap: true,
    // Zwei Produkte, ein Paket (AN0, docs/PLAN_ANALYSE.md 3): index.html ist der Hauskonfigurator,
    // analyse.html „Emprise Analyse“. Welche Seite ein Stack ausliefert, entscheidet SPA_INDEX im Caddyfile.
    rollupOptions: { input: { index: "index.html", analyse: "analyse.html" } },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});

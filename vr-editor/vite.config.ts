import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// API is deliberately same-origin in deployed environments. Development uses
// only the separately authenticated PlanReader API, never a public demo server.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
  },
  build: { outDir: "dist", sourcemap: false },
});

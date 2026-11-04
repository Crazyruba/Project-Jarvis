import { defineConfig } from "vite";

// The HUD runs on the same machine as OpenClaw. A loopback origin
// (http://localhost:5173) is accepted by the Gateway for local clients.
export default defineConfig({
  server: { host: "localhost", port: 5173 },
  preview: { host: "localhost", port: 4173 },
  build: { target: "es2022", chunkSizeWarningLimit: 1200 },
});

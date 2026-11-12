import { reactRouter } from "@react-router/dev/vite";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [reactRouter()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  // dev only: the API on this machine (uvicorn on 8000) answers /api, as nginx and Easypanel do in production
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});

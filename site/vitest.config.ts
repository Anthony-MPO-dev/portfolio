import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Unit tests only need the "@" alias, not the React Router plugin.
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
});

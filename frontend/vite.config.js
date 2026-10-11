import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: fileURLToPath(new URL("../req2test/static/", import.meta.url)),
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  root: fileURLToPath(new URL(".", import.meta.url)),
  server: {
    fs: {
      allow: [projectRoot],
    },
  },
});

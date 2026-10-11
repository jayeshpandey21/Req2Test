import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import process from "node:process";

const projectRoot = fileURLToPath(new URL("..", import.meta.url));
const outputDir = process.env.VERCEL
  ? "dist"
  : fileURLToPath(new URL("../req2test/static/", import.meta.url));

export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: outputDir,
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

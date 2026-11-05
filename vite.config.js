import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    base: env.VITE_BASE_PATH || "/",
    plugins: [react()],
    server: {
      port: 5173,
      // Forward /api to a local backend while developing (optional).
      proxy: env.VITE_DEV_API_PROXY
        ? { "/api": { target: env.VITE_DEV_API_PROXY, changeOrigin: true } }
        : undefined,
    },
    build: {
      target: "es2022",
      sourcemap: false,
    },
    test: {
      environment: "node",
      include: ["src/**/*.test.js"],
    },
  };
});

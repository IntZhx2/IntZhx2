import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      "/api": {
        target: process.env.DESKMATE_BACKEND || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: process.env.DESKMATE_BACKEND || "http://127.0.0.1:8000",
        ws: true,
      },
    },
  },
  test: { environment: "jsdom", clearMocks: true },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ["vue", "pinia"],
          charts: ["echarts"],
          markdown: ["marked", "dompurify", "highlight.js"],
        },
      },
    },
  },
});

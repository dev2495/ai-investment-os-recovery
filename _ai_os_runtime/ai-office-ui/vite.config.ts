import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Vite config — AI Investment Office Terminal (v2, now canonical).
 *
 * Serves on 127.0.0.1:5177 — the port the launchd UI service expects, so
 * cutover required zero launchd changes.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5177,
    strictPort: true,
  },
  build: {
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes("/three/") || id.includes("@react-three/")) return "vendor-three";
            if (id.includes("/react/") || id.includes("/react-dom/") || id.includes("react-router")) return "vendor-react";
            if (id.includes("@tanstack/react-query")) return "vendor-query";
            if (id.includes("/recharts/") || id.includes("d3-")) return "vendor-charts";
            if (id.includes("/cmdk/")) return "vendor-cmdk";
            if (id.includes("/lucide-react/")) return "vendor-icons";
            return "vendor";
          }
        },
      },
    },
  },
});

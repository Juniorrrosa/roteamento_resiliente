import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em dev (`npm run dev`), proxia /api -> backend local (localhost:8000).
// Em produção, quem proxia /api e o nginx do container (ver nginx.conf).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});

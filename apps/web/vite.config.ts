import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Durante `vite dev`, todo lo que pegue a /api se reenvía a la API real
// (apps/api, corriendo en el puerto 8000). Así el código del cliente siempre
// usa rutas relativas "/api/...", igual que en producción (donde la API sirve
// el build de este frontend desde el mismo origen, ver apps/api/Dockerfile).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});

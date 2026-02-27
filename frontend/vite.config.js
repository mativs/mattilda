import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const frontendUrl = process.env.FRONTEND_URL;
const frontendHost = (() => {
  if (!frontendUrl) return null;
  try {
    return new URL(frontendUrl).hostname;
  } catch {
    return frontendUrl;
  }
})();

const allowedHosts = [frontendHost, process.env.RAILWAY_PUBLIC_DOMAIN, "localhost", "127.0.0.1"].filter(Boolean);

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    allowedHosts,
  },
  preview: {
    host: "0.0.0.0",
    port: 3000,
    allowedHosts,
  },
});

import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy target can be overridden with VITE_PROXY_TARGET (default http://localhost:8000).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const target = env.VITE_PROXY_TARGET || 'http://localhost:8000'
  // SPA routes (/queue, /display, /admin/...) share prefixes with API paths.
  // Browser page loads (Accept: text/html) must get index.html, not the backend.
  const http = {
    target,
    changeOrigin: true,
    bypass: (req: { headers: { accept?: string } }) =>
      req.headers.accept?.includes('text/html') ? '/index.html' : undefined,
  }
  return {
    plugins: [react()],
    server: {
      port: 5174,
      proxy: {
        '/auth': http,
        '/queue': http,
        '/display': http,
        '/admin': http,
        '/departments': http,
        '/tts': http,
        '/ws': { target, changeOrigin: true, ws: true },
      },
    },
  }
})

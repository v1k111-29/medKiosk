import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy target can be overridden with VITE_PROXY_TARGET (default http://localhost:8000).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const target = env.VITE_PROXY_TARGET || 'http://localhost:8000'
  const http = { target, changeOrigin: true }
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
        '/ws': { target, changeOrigin: true, ws: true },
      },
    },
  }
})

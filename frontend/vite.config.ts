import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  server: {
    // Proxy API calls to FastAPI during dev (npm run dev)
    // This means relative URLs like /register work whether on :5173 or :8000
    proxy: {
      '/identify':      { target: 'http://localhost:8000', changeOrigin: true },
      '/register':      { target: 'http://localhost:8000', changeOrigin: true },
      '/transcribe':    { target: 'http://localhost:8000', changeOrigin: true },
      '/vitals':        { target: 'http://localhost:8000', changeOrigin: true },
      '/conversation':  { target: 'http://localhost:8000', changeOrigin: true },
      '/patients':      { target: 'http://localhost:8000', changeOrigin: true },
      '/health':        { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})

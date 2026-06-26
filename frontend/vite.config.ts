import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev server proxies API + media calls to the FastAPI backend on :8765, so the
// React app (on :5173) talks to the same origin it will in production.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8765',
      '/media': 'http://localhost:8765',
    },
  },
  build: { outDir: 'dist' },
})

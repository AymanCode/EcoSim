import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          charts: ['recharts'],
          icons: ['lucide-react'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    environmentOptions: {
      jsdom: {
        url: 'http://localhost:5173/',
      },
    },
    globals: true,
    setupFiles: './src/test/setup.js',
  },
  server: {
    allowedHosts: true,
    proxy: {
      '/ws': {
        target: 'ws://127.0.0.1:8002',
        ws: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8002',
      },
    },
  },
})

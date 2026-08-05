import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Function form rather than the object shorthand: Vite 8 builds on
        // rolldown, which only accepts a function here.
        manualChunks(id) {
          if (id.includes('node_modules/recharts')) return 'charts'
          if (id.includes('node_modules/lucide-react')) return 'icons'
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

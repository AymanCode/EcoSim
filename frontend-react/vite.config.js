import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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

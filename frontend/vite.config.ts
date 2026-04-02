import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/auth': 'http://localhost:8000',
      '/jobs': 'http://localhost:8000',
      '/applications': 'http://localhost:8000',
      '/cv': 'http://localhost:8000',
      '/integrations': 'http://localhost:8000',
    },
  },
})

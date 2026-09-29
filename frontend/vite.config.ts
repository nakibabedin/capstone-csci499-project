import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Forward /api requests to the Flask backend during development
    proxy: {
      '/api': 'http://localhost:5001',
    },
  },
})

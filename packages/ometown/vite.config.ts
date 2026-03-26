import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'dist',
    assetsInlineLimit: 4096, // Inline small assets < 4KB
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8765', // ome-server
      '/ws': { target: 'ws://localhost:8765', ws: true },
    },
  },
})

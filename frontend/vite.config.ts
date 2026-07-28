import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@shared': new URL('../shared', import.meta.url).pathname,
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
    // The design tokens live in ../shared, outside this project root.
    fs: { allow: ['..'] },
  },
  build: {
    outDir: 'dist',
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  // SPA is mounted at /dashboard on Cloud Run (not site root).
  // Absolute /assets/* was 404'ing into the Next marketing catch-all.
  base: '/dashboard/',
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
    rollupOptions: {
      input: {
        dashboard: new URL('./index.html', import.meta.url).pathname,
        approval: new URL('./approval.html', import.meta.url).pathname,
      },
    },
  },
})

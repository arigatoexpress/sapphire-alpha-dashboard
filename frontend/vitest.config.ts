import { defineConfig } from 'vitest/config'
import { fileURLToPath } from 'node:url'

/* The shared/ modules are pure TS with no DOM and no React, so they run in the
   default node environment. Tests live next to the modules they cover
   (`shared/__tests__`), outside this package's `src`, hence the explicit root. */
export default defineConfig({
  /* Keep the cache inside this package; the test root is the repository, and
     Vite would otherwise drop a node_modules/.vite at the repo root. */
  cacheDir: fileURLToPath(new URL('./node_modules/.vite', import.meta.url)),
  resolve: {
    alias: {
      '@shared': fileURLToPath(new URL('../shared', import.meta.url)),
    },
  },
  test: {
    root: fileURLToPath(new URL('..', import.meta.url)),
    include: ['shared/__tests__/**/*.test.ts'],
    environment: 'node',
  },
})

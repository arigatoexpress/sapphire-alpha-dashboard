import { defineConfig } from 'vitest/config'
import { fileURLToPath } from 'node:url'

/* The shared/ modules are pure TS with no DOM and no React, so they run in the
   default node environment. Tests live next to the modules they cover
   (`shared/__tests__`), outside this package's `src`, hence the explicit root.

   The desk's own tests live in `frontend/src/__tests__`. They also run in node:
   components are rendered with `react-dom/server`'s `renderToStaticMarkup`, so
   the assertions are made against real rendered markup without pulling in jsdom
   and a testing library. Nothing in the desk depends on layout effects, and the
   things worth asserting — that a null latency reads as "not measured", that no
   label box overlaps another — are all present in the static markup. */
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
    include: ['shared/__tests__/**/*.test.ts', 'frontend/src/**/*.test.{ts,tsx}'],
    environment: 'node',
  },
})

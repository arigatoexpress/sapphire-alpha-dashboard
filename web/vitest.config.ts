import { defineConfig } from 'vitest/config'
import { fileURLToPath } from 'node:url'

/**
 * Tests for the marketing site's own pure logic.
 *
 * `src/lib/machineRoom.ts` decides what every live figure *means* — including
 * whether there is a figure at all — so it is the part of the hero that can be
 * silently wrong. It runs in the node environment: the module is pure, and the
 * component is asserted through `react-dom/server`, which needs no DOM. That
 * keeps jsdom and a testing library out of the dependency list for assertions
 * that are all present in the static markup anyway (the same call the operator
 * desk's suite makes).
 *
 * `next build` does not read this file and the Dockerfile does not copy it;
 * vitest is a dev dependency only and never reaches the bundle.
 */
export default defineConfig({
  resolve: {
    alias: {
      '@shared': fileURLToPath(new URL('../shared', import.meta.url)),
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'node',
  },
})

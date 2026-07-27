import { defineConfig } from 'vitest/config'
import { fileURLToPath } from 'node:url'

/**
 * Tests for the marketing site's own pure logic.
 *
 * Pure page and component assertions run in Node through `react-dom/server`.
 * That keeps jsdom and a testing library out of the dependency list for
 * assertions already present in static markup.
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

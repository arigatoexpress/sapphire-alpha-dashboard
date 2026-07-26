import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { NextConfig } from 'next'

/**
 * Static export. The FastAPI container serves `web/out/` directly, so the
 * marketing site and the live dashboard stay on one Cloud Run service and one
 * domain. Every route becomes a prerendered HTML file — crawlers and social
 * unfurlers get full content without executing JavaScript.
 */
const nextConfig: NextConfig = {
  output: 'export',
  // Emits `out/<route>/index.html`, which is unambiguous to serve from Python.
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
  /**
   * The pure modules in `../shared` are imported by both surfaces through the
   * `@shared/*` alias in tsconfig.json. Turbopack applies that alias but then
   * refuses to resolve outside its inferred root, which is this directory
   * because `web/` carries its own lockfile — so the root is widened to the
   * repository. Without this, `@shared/...` type-checks and then fails the
   * build with "Module not found".
   */
  turbopack: {
    root: path.join(path.dirname(fileURLToPath(import.meta.url)), '..'),
  },
}

export default nextConfig

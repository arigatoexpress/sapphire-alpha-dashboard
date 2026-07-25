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
}

export default nextConfig

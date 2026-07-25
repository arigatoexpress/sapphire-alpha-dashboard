import type { MetadataRoute } from 'next'
import { SITE_URL } from '@/lib/site'

export const dynamic = 'force-static'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        // The operator dashboard and the API are not crawlable surfaces. They
        // are auth-gated regardless — this just keeps them out of indexes.
        disallow: ['/dashboard', '/api/', '/vault/', '/miniapp'],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  }
}

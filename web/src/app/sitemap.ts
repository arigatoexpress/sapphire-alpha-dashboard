import type { MetadataRoute } from 'next'
import { SITE_URL } from '@/lib/site'
import { MEASURED_AT } from '@/data/metrics'

export const dynamic = 'force-static'

/** Marketing routes only. The dashboard and API are excluded deliberately. */
const ROUTES: { path: string; priority: number }[] = [
  { path: '/', priority: 1 },
  { path: '/architecture/', priority: 0.9 },
  { path: '/trading/', priority: 0.8 },
  { path: '/security/', priority: 0.8 },
  { path: '/onchain/', priority: 0.7 },
  { path: '/about/', priority: 0.7 },
]

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date(MEASURED_AT)
  return ROUTES.map((route) => ({
    url: `${SITE_URL}${route.path}`,
    lastModified,
    changeFrequency: 'monthly' as const,
    priority: route.priority,
  }))
}

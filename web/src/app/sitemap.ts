import type { MetadataRoute } from 'next'
import { SITE_URL } from '@/lib/site'
import { MEASURED_AT } from '@/data/metrics'
import { getReports } from '@/lib/research'

export const dynamic = 'force-static'

/** Marketing routes only. The dashboard and API are excluded deliberately. */
const ROUTES: { path: string; priority: number }[] = [
  { path: '/', priority: 1 },
  { path: '/architecture/', priority: 0.9 },
  { path: '/trading/', priority: 0.8 },
  { path: '/security/', priority: 0.8 },
  { path: '/proof/', priority: 0.9 },
  { path: '/onchain/', priority: 0.7 },
  { path: '/research/', priority: 0.9 },
  { path: '/about/', priority: 0.7 },
]

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date(MEASURED_AT)

  const pages = ROUTES.map((route) => ({
    url: `${SITE_URL}${route.path}`,
    lastModified,
    changeFrequency: 'monthly' as const,
    priority: route.priority,
  }))

  // Each published report is its own indexable page, dated by the report itself
  // so a stale piece is visibly stale to a crawler.
  const reports = getReports().map((report) => ({
    url: `${SITE_URL}/research/${report.slug}/`,
    lastModified: report.date ? new Date(report.date) : lastModified,
    changeFrequency: 'yearly' as const,
    priority: 0.6,
  }))

  return [...pages, ...reports]
}

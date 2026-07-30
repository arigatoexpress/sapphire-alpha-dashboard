import type { MetadataRoute } from 'next'
import { SITE_URL } from '@/lib/site'
import { MEASURED_AT } from '@/data/metrics'
import { getReports } from '@/lib/research'

export const dynamic = 'force-static'

/**
 * Static routes for the marketing surface. The site is a single-page dashboard
 * plus one dynamic route per published research file. The operator dashboard
 * and every API path are deliberately excluded from the sitemap.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date(MEASURED_AT)

  const home = {
    url: `${SITE_URL}/`,
    lastModified,
    changeFrequency: 'daily' as const,
    priority: 1,
  }

  const reports = getReports().map((report) => ({
    url: `${SITE_URL}/research/${report.slug}/`,
    lastModified: report.date ? new Date(report.date) : lastModified,
    changeFrequency: 'yearly' as const,
    priority: 0.6,
  }))

  return [home, ...reports]
}

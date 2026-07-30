import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { getReport, getReports } from '@/lib/research'

type Params = { params: Promise<{ slug: string }> }

/** Static export needs every report route enumerated at build time. */
export async function generateStaticParams(): Promise<{ slug: string }[]> {
  return getReports().map((report) => ({ slug: report.slug }))
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params
  const report = getReport(slug)
  if (!report) return { title: 'Report not found' }

  return {
    title: report.title,
    description: report.description || undefined,
    alternates: { canonical: `/research/${report.slug}/` },
    openGraph: {
      type: 'article',
      title: report.title,
      description: report.description || undefined,
      publishedTime: report.date ?? undefined,
    },
  }
}

export default async function ReportPage({ params }: Params) {
  const { slug } = await params
  const report = getReport(slug)
  if (!report) notFound()

  return (
    <article className="report">
      <Link href="/#research" className="report-back">
        ← Back to research
      </Link>

      <header className="report-head">
        <p className="report-kicker">
          Research
          {report.date && <span> · {report.date}</span>}
          <span> · {report.minutes} min read</span>
        </p>
        <h1>{report.title}</h1>
        {report.description && <p className="report-lede">{report.description}</p>}
        {report.tags.length > 0 && (
          <ul className="report-tags" aria-label="Tags">
            {report.tags.map((tag) => (
              <li key={tag}>#{tag}</li>
            ))}
          </ul>
        )}
      </header>

      {/* HTML is sanitized through an allow-list in lib/research.ts before it
          reaches here — markdown is partly agent-authored, so it is treated as
          untrusted even though it is committed to this repo. */}
      <div className="prose-report" dangerouslySetInnerHTML={{ __html: report.html }} />

      <footer className="report-foot">
        <p>
          Analysis only. Nothing here is investment advice, an offer, or a
          solicitation. Current positions and exact figures are operator-only
          and do not appear in published research.
        </p>
        <Link href="/#research" className="report-back">
          ← All research
        </Link>
      </footer>
    </article>
  )
}

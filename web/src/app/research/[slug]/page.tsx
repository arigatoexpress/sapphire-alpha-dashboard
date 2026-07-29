import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { Eyebrow } from '@/components/Primitives'
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
    other:
      report.sources.length > 0
        ? { citation: report.sources.map((source) => source.url) }
        : undefined,
  }
}

export default async function ReportPage({ params }: Params) {
  const { slug } = await params
  const report = getReport(slug)
  if (!report) notFound()

  return (
    <article className="mx-auto max-w-3xl px-6 pt-20 pb-8 md:pt-28">
      <Link
        href="/research/"
        className="underline-grow font-mono text-[11px] tracking-[0.14em] text-ink-dim uppercase transition-colors hover:text-ink"
      >
        ← Research
      </Link>

      <header className="mt-10">
        <Eyebrow>{report.date ?? 'Undated'}</Eyebrow>
        <h1 className="rise mt-5 font-display text-4xl leading-[1.02] font-semibold tracking-[-0.03em] text-balance md:text-6xl">
          {report.title}
        </h1>
        {report.description && (
          <p className="mt-6 text-lg leading-relaxed text-ink-dim text-pretty">
            {report.description}
          </p>
        )}
        <p className="mt-6 font-mono text-[11px] tracking-[0.1em] text-ink-faint uppercase">
          {report.minutes} min read
          {report.tags.length > 0 && <> · {report.tags.join(' · ')}</>}
        </p>
        {report.sources.length > 0 && (
          <nav aria-label="Authoritative sources" className="mt-6">
            <p className="font-mono text-[10px] tracking-[0.14em] text-ink-faint uppercase">
              Authoritative sources
            </p>
            <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
              {report.sources.map((source) => (
                <li key={source.url}>
                  <a
                    href={source.url}
                    className="underline-grow text-sm text-sapphire"
                    rel="noreferrer"
                  >
                    {source.label} ↗
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </header>

      <div className="rule my-12" aria-hidden="true" />

      {/* HTML is sanitized through an allow-list in lib/research.ts before it
          reaches here — the markdown is partly agent-authored, so it is treated
          as untrusted even though it is committed to this repo. */}
      <div className="prose-report" dangerouslySetInnerHTML={{ __html: report.html }} />

      <div className="rule my-14" aria-hidden="true" />

      <footer className="pb-4">
        <p className="text-sm leading-relaxed text-ink-faint">
          Analysis only. Nothing here is investment advice, an offer, or a solicitation.
          Current positions and exact figures are operator-only and do not appear in
          published research.
        </p>
        <Link
          href="/research/"
          className="underline-grow mt-6 inline-block font-mono text-[11px] tracking-[0.14em] text-sapphire uppercase"
        >
          ← All research
        </Link>
      </footer>
    </article>
  )
}

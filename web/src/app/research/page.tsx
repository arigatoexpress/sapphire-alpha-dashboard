import type { Metadata } from 'next'
import Link from 'next/link'
import { Eyebrow, PageHeader, Panel, Rule } from '@/components/Primitives'
import { getReports } from '@/lib/research'

export const metadata: Metadata = {
  title: 'Research',
  description:
    'Published research under the Michael Nadeau / DeFi Report lens: real fees, whether ' +
    'the token captures them, and net supply. Framework and retrospective — never the live book.',
  alternates: { canonical: '/research/' },
}

/* The four questions every published report has to answer. Stated on the index
   so a reader can hold the work to them before reading a word of it. */
const STANDARD = [
  {
    n: '01',
    title: 'Does it earn real fees?',
    body: 'Revenue paid by users, not emissions dressed up as yield.',
  },
  {
    n: '02',
    title: 'Does the token capture them?',
    body: 'A protocol earning is not the same as the liquid token having a claim on it.',
  },
  {
    n: '03',
    title: 'What is net supply doing?',
    body: 'Buybacks net of emissions and vesting. A burn headline means nothing gross.',
  },
  {
    n: '04',
    title: 'What would prove this wrong?',
    body: 'Falsifiers committed before the outcome, so the call can actually be scored.',
  },
]

export default function Research() {
  const reports = getReports()

  return (
    <>
      <PageHeader
        eyebrow="Research"
        title="Positions are private. The reasoning is not."
        lede="Published work applies the Nadeau lens — real fees, token capture, net supply — and commits to what would prove it wrong. What is never published is the live book: current holdings and sizing stay operator-only."
      />

      <section className="mx-auto max-w-6xl px-6 pt-14" aria-labelledby="standard-heading">
        <Eyebrow>The standard</Eyebrow>
        <h2
          id="standard-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-4xl"
        >
          Four questions, asked of everything.
        </h2>

        <div className="mt-12 grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
          {STANDARD.map((item) => (
            <div key={item.n} className="bg-void p-6 md:p-7">
              <p className="tnum font-mono text-[11px] tracking-[0.2em] text-sapphire">{item.n}</p>
              <h3 className="mt-5 font-display text-lg leading-snug font-semibold tracking-[-0.01em]">
                {item.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-ink-dim">{item.body}</p>
            </div>
          ))}
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="reports-heading">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <Eyebrow>Published</Eyebrow>
            <h2
              id="reports-heading"
              className="mt-4 font-display text-3xl font-semibold tracking-[-0.02em] md:text-4xl"
            >
              Reports
            </h2>
          </div>
          {reports.length > 0 && (
            <p className="tnum font-mono text-[11px] text-ink-faint">
              {reports.length} published
            </p>
          )}
        </div>

        {reports.length === 0 ? (
          <Panel className="mt-12">
            <p className="font-mono text-[11px] tracking-[0.16em] text-ink-faint uppercase">
              Nothing published yet
            </p>
            <p className="mt-5 max-w-2xl text-sm leading-relaxed text-ink-dim">
              This page is deliberately empty rather than seeded with samples. Research
              publishes only when a report is explicitly marked for publication — the
              research vault also holds machine-generated notes that are not reliable, and
              an empty page is a far better failure mode than a confident wrong one.
            </p>
          </Panel>
        ) : (
          <div className="mt-12 border-t border-line-lit">
            {reports.map((report, i) => (
              <Link
                key={report.slug}
                href={`/research/${report.slug}/`}
                className="rise group grid gap-3 border-b border-line py-7 transition-colors hover:bg-raised/40 md:grid-cols-[150px_1fr] md:gap-8"
                style={{ animationDelay: `${i * 70}ms` }}
              >
                <p className="tnum font-mono text-[12px] text-ink-faint">
                  {report.date ?? '—'}
                </p>
                <div>
                  <h3 className="font-display text-xl leading-snug font-semibold tracking-[-0.015em] transition-colors group-hover:text-sapphire">
                    {report.title}
                  </h3>
                  {report.description && (
                    <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-dim">
                      {report.description}
                    </p>
                  )}
                  <p className="mt-3 font-mono text-[11px] tracking-[0.1em] text-ink-faint uppercase">
                    {report.minutes} min read
                    {report.tags.length > 0 && <> · {report.tags.slice(0, 3).join(' · ')}</>}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6">
        <Panel>
          <Eyebrow>What is withheld, and why</Eyebrow>
          <div className="mt-6 grid gap-8 md:grid-cols-2">
            <p className="text-sm leading-relaxed text-ink-dim">
              Current holdings, sizing, and exact capital figures are excluded from this
              corpus. The public architecture feed is a separate contract and contains none
              of them; a real-time public book would invite front-running.
            </p>
            <p className="text-sm leading-relaxed text-ink-dim">
              What that leaves is the part worth reading anyway: the framework, and closed
              calls scored against falsifiers committed in advance. A method you can apply
              yourself is more useful than a ticker you cannot check.
            </p>
          </div>
        </Panel>
      </section>
    </>
  )
}

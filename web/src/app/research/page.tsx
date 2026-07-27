import type { Metadata } from 'next'
import Link from 'next/link'
import { Eyebrow, PageHeader, Panel, Rule } from '@/components/Primitives'
import { ConceptCards, MethodFlow, PathBandChart, ProbabilityRing } from '@/components/Visuals'
import { getReports } from '@/lib/research'

export const metadata: Metadata = {
  title: 'Research',
  description:
    'A private investment mandate tested against cycle, liquidity, market structure, ' +
    'technology, and protocol-fundamentals evidence. Framework and retrospective — never the live book.',
  alternates: { canonical: '/research/' },
}

/* The four questions every published report has to answer. Stated on the index
   so a reader can hold the work to them before reading a word of it. */
const STANDARD = [
  {
    n: '01',
    title: 'What does the data say?',
    body: 'Public market feeds and portfolio multi-lens scores first — prices, dominance, macro proxies, cluster risk.',
  },
  {
    n: '02',
    title: 'What is our event probability?',
    body: 'Binary claims get one probability as of the timestamp (e.g. “cycle low is in”). Not short/med/long odds.',
  },
  {
    n: '03',
    title: 'What is the path?',
    body: 'Short / medium / long horizons are for price bands, growth, and trends — with scenarios, not fake precision.',
  },
  {
    n: '04',
    title: 'What would prove us wrong?',
    body: 'Every claim carries a falsifier before the outcome so the system can learn, not just narrate.',
  },
]

export default function Research() {
  const reports = getReports()

  return (
    <>
      <PageHeader
        eyebrow="Research"
        title="Data first. Then a clear opinion."
        lede="We publish event probabilities as of a timestamp, path forecasts for targets and trends, and the evidence and falsifiers behind both. Positions stay private. Reasoning does not."
      />

      <section className="mx-auto max-w-6xl px-6 pt-6">
        <p className="text-sm text-ink-dim">
          Full research contract:{" "}
          <Link
            href="/research/research-methodology/"
            className="text-sapphire underline-offset-4 hover:underline"
          >
            How we form market opinions
          </Link>
          .
        </p>
      </section>

      {/* Visual: event P vs path band */}
      <section className="mx-auto max-w-6xl px-6 pt-14" aria-labelledby="viz-heading">
        <Eyebrow>See the difference</Eyebrow>
        <h2
          id="viz-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-4xl"
        >
          One probability for events. Bands for paths.
        </h2>
        <div className="home-viz-row mt-10">
          <ProbabilityRing p={0.51} label="BTC cycle low is in" sub="As of latest book · residual 49%" />
          <ProbabilityRing p={0.63} label="4-year cycle still useful" sub="Lean yes · prior + position" />
          <div className="w-full">
            <PathBandChart
              asset="BTC"
              horizon="medium · 90d path"
              spot={65175}
              bear={46926}
              base={66500}
              bull={85000}
            />
            <p className="home-viz-caption">
              Short / medium / long horizons never rewrite the event probability. They only describe
              possible price paths and trends.
            </p>
          </div>
        </div>
        <div className="mt-12">
          <ConceptCards />
        </div>
        <div className="mt-10">
          <MethodFlow />
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6 pt-4" aria-labelledby="standard-heading">
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
          <>
            {/* Featured strip: latest system opinions + portfolio cards first */}
            <div className="mt-12 grid gap-px border border-line-lit bg-line md:grid-cols-2">
              {reports.slice(0, 2).map((report) => {
                const isOpinion =
                  report.tags.includes('conjecture') ||
                  report.tags.includes('predictions') ||
                  report.slug.includes('conjecture')
                const isBook =
                  report.tags.includes('portfolio') || report.slug.includes('portfolio')
                const kicker = isBook
                  ? 'Portfolio multi-lens'
                  : isOpinion
                    ? 'System opinions'
                    : 'Research'
                return (
                  <Link
                    key={`feat-${report.slug}`}
                    href={`/research/${report.slug}/`}
                    className="group relative flex flex-col justify-between bg-void p-7 transition-colors hover:bg-raised md:p-9"
                  >
                    <div>
                      <p className="font-mono text-[10px] tracking-[0.18em] text-ice uppercase">
                        {kicker}
                      </p>
                      <h3 className="mt-4 max-w-md font-conviction text-3xl leading-[0.95] font-medium tracking-[-0.03em] text-ink transition-colors group-hover:text-sapphire md:text-4xl">
                        {report.title}
                      </h3>
                      {report.description && (
                        <p className="mt-5 max-w-lg text-sm leading-relaxed text-ink-dim text-pretty">
                          {report.description}
                        </p>
                      )}
                    </div>
                    <p className="mt-8 font-mono text-[11px] tracking-[0.12em] text-ink-faint uppercase">
                      {report.date ?? '—'} · {report.minutes} min · read →
                    </p>
                  </Link>
                )
              })}
            </div>

            <div className="mt-10 border-t border-line-lit">
              {reports.map((report, i) => (
                <Link
                  key={report.slug}
                  href={`/research/${report.slug}/`}
                  className="rise group grid gap-3 border-b border-line py-7 transition-colors hover:bg-raised/40 md:grid-cols-[150px_1fr_auto] md:items-baseline md:gap-8"
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
                    <div className="mt-3 flex flex-wrap gap-2">
                      {report.tags.slice(0, 5).map((tag) => (
                        <span
                          key={tag}
                          className="border border-line px-2 py-0.5 font-mono text-[10px] tracking-[0.1em] text-ink-faint uppercase"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                  <p className="font-mono text-[11px] tracking-[0.1em] text-ink-faint uppercase md:text-right">
                    {report.minutes} min
                  </p>
                </Link>
              ))}
            </div>
          </>
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

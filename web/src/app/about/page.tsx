import type { Metadata } from 'next'
import Link from 'next/link'
import { Eyebrow, PageHeader, Panel, Row, Rule, Verified } from '@/components/Primitives'
import { MEASURED_AT, MEASURED_SHA } from '@/data/metrics'

export const metadata: Metadata = {
  title: 'About',
  description:
    'Sapphire Alpha builds autonomous agent and trading infrastructure where correctness ' +
    'is the product. Engagements, principles, and how to get in touch.',
  alternates: { canonical: '/about/' },
}

const PRINCIPLES = [
  {
    term: 'Tests are the spec',
    body:
      'Behaviour is pinned by the suite before it is refactored. If a property matters, it ' +
      'is asserted — documentation alone is not a control.',
  },
  {
    term: 'Delete before adding',
    body:
      'Fewer dependencies, fewer abstractions, fewer moving parts. A shared module earns ' +
      'its existence at the second real call site, not the first imagined one.',
  },
  {
    term: 'Reversible by default',
    body:
      'Small diffs, one concern at a time, and a path back from every change. Irreversible ' +
      'steps get a human gate rather than a confirmation dialog.',
  },
  {
    term: 'Fail closed',
    body:
      'When a check cannot run, the answer is stop. Systems that degrade toward permissive ' +
      'are the ones that surprise you at 3am.',
  },
]

const ENGAGEMENTS = [
  {
    title: 'Autonomous agent systems',
    body:
      'Multi-agent orchestration that runs unattended without becoming unauditable — ' +
      'fences, approval rails, durable checkpoints, and the tests that keep them honest.',
  },
  {
    title: 'Trading & execution rails',
    body:
      'Signal-to-fill pipelines with hard caps, kill switches, and privacy-preserving ' +
      'telemetry. Including the unglamorous parts: reconciliation, replay, and staleness.',
  },
  {
    title: 'Verification discipline',
    body:
      'Turning a codebase that mostly works into one that can prove it does. Characterization ' +
      'tests, golden fixtures, and CI that actually blocks.',
  },
]

export default function About() {
  return (
    <>
      <PageHeader
        eyebrow="About"
        title="Correctness is the product."
        lede="Sapphire Alpha is an independent engineering practice building research and trading infrastructure with fail-closed boundaries — the kind that has to be right while nobody is watching it."
      />

      <section className="mx-auto max-w-6xl px-6 pt-14">
        <div className="grid gap-12 lg:grid-cols-[1fr_1fr] lg:gap-16">
          <div className="space-y-5 text-base leading-relaxed text-ink-dim md:text-lg">
            <p>
              Most systems in this space are demonstrated rather than examined. They look
              excellent in a recorded walkthrough and become opaque the moment you ask what
              happens when a check times out.
            </p>
            <p>
              The work here starts from the opposite end: define the failure modes, pin them
              with tests, and only then make the thing fast. It is slower to build and
              considerably cheaper to operate.
            </p>
            <p className="text-ink">
              The result is infrastructure you can hand to someone else without a briefing.
            </p>
          </div>

          <Panel>
            <Eyebrow>Engagements</Eyebrow>
            <div className="mt-7 space-y-7">
              {ENGAGEMENTS.map((engagement) => (
                <div key={engagement.title}>
                  <h3 className="font-display text-lg font-semibold tracking-[-0.01em]">
                    {engagement.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-dim">{engagement.body}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="principles-heading">
        <Eyebrow>How the work is done</Eyebrow>
        <h2
          id="principles-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
        >
          Four rules, applied without exception.
        </h2>
        <dl className="mt-12 border-t border-line">
          {PRINCIPLES.map((principle) => (
            <Row key={principle.term} term={principle.term}>
              {principle.body}
            </Row>
          ))}
        </dl>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="contact-heading">
        <div className="border border-line-lit bg-raised/40 px-7 py-14 md:px-16 md:py-20">
          <div className="mx-auto max-w-2xl text-center">
            <Eyebrow>Contact</Eyebrow>
            <h2
              id="contact-heading"
              className="mt-5 font-display text-3xl leading-tight font-semibold tracking-[-0.025em] text-balance md:text-5xl"
            >
              Bring a hard problem.
            </h2>
            <p className="mt-6 text-base leading-relaxed text-ink-dim text-pretty">
              The best fit is work where being wrong is expensive and &ldquo;it seemed fine in
              testing&rdquo; is not an acceptable post-mortem.
            </p>

            <div className="mt-10 flex flex-wrap justify-center gap-4">
              <Link
                href="/research/"
                className="border border-sapphire bg-sapphire px-6 py-3 font-mono text-[12px] tracking-[0.14em] text-void uppercase transition-colors hover:bg-transparent hover:text-sapphire"
              >
                Read the research
              </Link>
              <Link
                href="/architecture/"
                className="border border-line-lit px-6 py-3 font-mono text-[12px] tracking-[0.14em] text-ink-dim uppercase transition-colors hover:border-sapphire hover:text-ink"
              >
                Read the architecture
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pt-16">
        <div className="flex flex-wrap items-center justify-between gap-6 border-t border-line pt-8">
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            <Verified>Figures reproducible</Verified>
            <Verified>Commit {MEASURED_SHA}</Verified>
          </div>
          <p className="font-mono text-[11px] text-ink-faint">
            last measured <span className="tnum text-ink-dim">{MEASURED_AT}</span>
          </p>
        </div>
      </section>
    </>
  )
}

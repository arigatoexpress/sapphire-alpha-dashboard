import Link from 'next/link'
import CommandDesk from '@/components/CommandDesk'
import MetricCard from '@/components/Metric'
import { Eyebrow, Rule, Verified } from '@/components/Primitives'
import { CHAIN, CORE_METRICS, MEASURED_AT } from '@/data/metrics'

const LENSES = [
  {
    n: '01',
    title: 'Portfolio multi-lens',
    body: 'Quant, narrative, cluster risk, and falsifiers on one book — not market tourism.',
    href: '/research/',
  },
  {
    n: '02',
    title: 'Free-reign agentic',
    body: 'RH Agentic MCP auto-executes on designated capital under account-scale envelopes.',
    href: '/trading/',
  },
  {
    n: '03',
    title: 'Living plant map',
    body: 'Architecture telemetry, agent graph, and host duties — measurable, not decorative.',
    href: '/architecture/',
  },
  {
    n: '04',
    title: 'Operator desk',
    body: 'Real-time dashboard: decisions, evidence, assets, and system posture in one view.',
    href: '/dashboard',
  },
]

export default function Home() {
  return (
    <>
      <CommandDesk />

      <Rule />

      <section className="mx-auto max-w-[1440px] px-5 md:px-8" aria-labelledby="lenses-heading">
        <Eyebrow>Analyze the whole system</Eyebrow>
        <h2
          id="lenses-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
        >
          A place to see what we built — not a brochure.
        </h2>
        <div className="mt-12 grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
          {LENSES.map((lens) => (
            <Link
              key={lens.n}
              href={lens.href}
              className="group flex flex-col justify-between bg-void p-7 transition-colors hover:bg-raised md:p-8"
            >
              <div>
                <p className="tnum font-mono text-[11px] tracking-[0.2em] text-sapphire">{lens.n}</p>
                <h3 className="mt-5 font-display text-xl font-semibold tracking-[-0.015em] group-hover:text-sapphire">
                  {lens.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-ink-dim">{lens.body}</p>
              </div>
              <p className="mt-8 font-mono text-[11px] tracking-[0.12em] text-ink-faint uppercase transition-colors group-hover:text-sapphire">
                Open →
              </p>
            </Link>
          ))}
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-[1440px] px-5 md:px-8" aria-labelledby="metrics-heading">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <Eyebrow>Measured, not estimated</Eyebrow>
            <h2
              id="metrics-heading"
              className="mt-4 font-display text-3xl font-semibold tracking-[-0.02em] md:text-4xl"
            >
              The system, counted.
            </h2>
          </div>
          <p className="font-mono text-[11px] text-ink-faint">
            counted <span className="tnum text-ink-dim">{MEASURED_AT}</span>
          </p>
        </div>
        <div className="mt-12 grid gap-x-10 gap-y-14 sm:grid-cols-2 lg:grid-cols-4">
          {CORE_METRICS.map((metric, i) => (
            <MetricCard key={metric.label} metric={metric} index={i} />
          ))}
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-[1440px] px-5 pb-20 md:px-8">
        <div className="grid gap-10 border border-line bg-raised/40 p-8 md:grid-cols-[1.1fr_0.9fr] md:p-12">
          <div>
            <Eyebrow>Settlement</Eyebrow>
            <h2 className="mt-4 font-display text-3xl font-semibold tracking-[-0.02em] md:text-4xl">
              {CHAIN.name} · chain {CHAIN.id}
            </h2>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-ink-dim">
              On-chain legs settle on an {CHAIN.family}. Brokerage legs clear through Robinhood
              Agentic MCP on the designated agentic account only. Client money never shares these
              rails.
            </p>
            <div className="mt-7 flex flex-wrap gap-x-6 gap-y-3">
              <Verified>Wallet fenced</Verified>
              <Verified>Kill switch</Verified>
              <Verified>Account-scale free-reign</Verified>
            </div>
          </div>
          <div className="border border-line bg-void p-6 font-mono text-[12px] leading-relaxed text-ink-dim md:p-8">
            <p className="text-ink-faint">// public contract</p>
            <p className="mt-3 text-sapphire">mode: free-reign easy</p>
            <p>planner: grok-super-heavy → nemotron</p>
            <p>brokerage: rh-agentic-mcp</p>
            <p>onchain: rh-chain-l2</p>
            <p>hard_stops: killswitch · wallet_fence</p>
            <p className="mt-4 text-ink-faint">// capital state omitted from anonymous views</p>
          </div>
        </div>
      </section>
    </>
  )
}

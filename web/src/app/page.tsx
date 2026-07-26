import Link from 'next/link'
import MetricCard from '@/components/Metric'
import MachineRoom from '@/components/MachineRoom'
import { Eyebrow, Panel, Rule, Verified } from '@/components/Primitives'
import { CHAIN, CORE_METRICS, MEASURED_AT } from '@/data/metrics'

const CAPABILITIES = [
  {
    n: '01',
    title: 'Autonomous execution',
    body:
      'Agents that analyse, propose, and execute against hard per-trade and daily caps. ' +
      'Every action is bounded before it is fast.',
    href: '/trading/',
  },
  {
    n: '02',
    title: 'Fail-closed safety',
    body:
      'A kill switch, a human approval rail, and a fence list that binds every agent in ' +
      'the fleet. When a check cannot run, execution stops.',
    href: '/security/',
  },
  {
    n: '03',
    title: 'On-chain settlement',
    body:
      `Positions settle on ${CHAIN.name} (chain ${CHAIN.id}), an ${CHAIN.family}. ` +
      'Wallet identifiers never enter an anonymous response.',
    href: '/onchain/',
  },
]

export default function Home() {
  return (
    <>
      {/* ------------------------------------------------------------------
          THE MACHINE ROOM

          The landing page used to describe the system in prose beside a small
          status panel. It now *is* the system: the running machine is the first
          thing a visitor meets, it explains its own parts in plain English, and
          it says out loud which of its numbers are measured and which are not.
          The prose that survived is the part the picture cannot say — what the
          work is for, and what we are willing to be held to.
          ------------------------------------------------------------------ */}
      <section className="mx-auto w-full max-w-[1680px] px-5 pt-14 pb-4 md:px-10 md:pt-20">
        <div className="rise max-w-4xl">
          <Eyebrow>{CHAIN.name} · chain {CHAIN.id}</Eyebrow>
          <h1 className="mt-6 font-display text-5xl leading-[0.92] font-semibold tracking-[-0.035em] text-balance md:text-7xl">
            Verify,
            <br />
            don&rsquo;t&nbsp;<span className="text-sapphire">trust</span>.
          </h1>
          <p className="mt-7 max-w-2xl text-lg leading-relaxed text-ink-dim text-pretty">
            Below is the system&rsquo;s declared map and its latest live report. Every part
            says what it is in plain English. A line moves only when the feed supplies an
            exact rate; older banded reports stay still, and missing figures say so.
          </p>
        </div>

        <div className="rise mt-14 md:mt-16" style={{ animationDelay: '120ms' }}>
          <MachineRoom />
        </div>

        <div className="mt-14 flex flex-wrap items-center gap-4">
          <Link
            href="/architecture/"
            className="border border-sapphire bg-sapphire px-6 py-3 font-mono text-[12px] tracking-[0.14em] text-void uppercase transition-colors hover:bg-transparent hover:text-sapphire"
          >
            Read the architecture
          </Link>
          <Link
            href="/dashboard"
            className="underline-grow px-1 py-3 font-mono text-[12px] tracking-[0.14em] text-ink-dim uppercase transition-colors hover:text-ink"
          >
            Open the live desk →
          </Link>
        </div>
      </section>

      <Rule />

      {/* ---------------- Metrics ---------------- */}
      <section
        className="mx-auto max-w-6xl px-6"
        aria-labelledby="metrics-heading"
      >
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

        <p className="mt-12 max-w-2xl text-sm leading-relaxed text-ink-faint">
          Each of these says exactly what it counts. &ldquo;Test functions
          defined&rdquo; is not the same claim as &ldquo;tests passing,&rdquo; and we use the
          narrower one — the honest version of a number is usually the less impressive one.
        </p>
      </section>

      <Rule />

      {/* ---------------- Capabilities ---------------- */}
      <section className="mx-auto max-w-6xl px-6" aria-labelledby="capabilities-heading">
        <Eyebrow>What it does</Eyebrow>
        <h2
          id="capabilities-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
        >
          Three guarantees, in the order they matter.
        </h2>

        <div className="mt-14 grid gap-px border border-line bg-line md:grid-cols-3">
          {CAPABILITIES.map((cap) => (
            <Link
              key={cap.n}
              href={cap.href}
              className="group flex flex-col justify-between bg-void p-7 transition-colors hover:bg-raised md:p-9"
            >
              <div>
                <p className="tnum font-mono text-[11px] tracking-[0.2em] text-sapphire">
                  {cap.n}
                </p>
                <h3 className="mt-6 font-display text-2xl font-semibold tracking-[-0.015em]">
                  {cap.title}
                </h3>
                <p className="mt-4 text-sm leading-relaxed text-ink-dim">{cap.body}</p>
              </div>
              <p className="mt-10 font-mono text-[11px] tracking-[0.14em] text-ink-faint uppercase transition-colors group-hover:text-sapphire">
                Read more →
              </p>
            </Link>
          ))}
        </div>
      </section>

      <Rule />

      {/* ---------------- Thesis ---------------- */}
      <section className="mx-auto max-w-6xl px-6" aria-labelledby="thesis-heading">
        <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:gap-20">
          <div>
            <Eyebrow>The position</Eyebrow>
            <h2
              id="thesis-heading"
              className="mt-4 font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
            >
              Most trading infrastructure asks for faith.
            </h2>
          </div>

          <div className="space-y-6 text-base leading-relaxed text-ink-dim md:text-lg">
            <p>
              Backtests get shown without the data behind them. Uptime gets asserted rather
              than displayed. &ldquo;Institutional-grade&rdquo; means whatever the pitch deck
              needs it to mean.
            </p>
            <p>
              This works the other way around. Before a position is taken, we write down what
              would prove the thesis wrong — and then that judgement gets scored against what
              actually happened.
            </p>
            <p className="text-ink">
              The claim is not that we are always right. It is that you can tell when we
              were not.
            </p>
          </div>
        </div>

        {/* Each of these is a property of the live endpoint the page above reads,
            so a reader can check all three against what they just watched. */}
        <Panel className="mt-14">
          <div className="grid gap-8 md:grid-cols-3">
            <div>
              <Verified>One telemetry contract</Verified>
              <p className="mt-3 text-sm leading-relaxed text-ink-dim">
                The Machine Room reads one architecture feed with numeric fields when they
                are available. Capital, wallet identifiers, and current holdings never enter
                that contract.
              </p>
            </div>
            <div>
              <Verified>Signed ingest</Verified>
              <p className="mt-3 text-sm leading-relaxed text-ink-dim">
                Reads are open; writes are not. Telemetry is signed and replay-rejected
                before it is ever stored.
              </p>
            </div>
            <div>
              <Verified>Fail-closed gates</Verified>
              <p className="mt-3 text-sm leading-relaxed text-ink-dim">
                A missing check is a stop, never a default-allow. The kill switch is a file.
              </p>
            </div>
          </div>
        </Panel>
      </section>

      <Rule />

      {/* ---------------- CTA ---------------- */}
      <section className="mx-auto max-w-6xl px-6">
        <div className="border border-line-lit bg-raised/40 px-7 py-14 text-center md:px-16 md:py-20">
          <Eyebrow>Engagements</Eyebrow>
          <h2 className="mx-auto mt-5 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.025em] text-balance md:text-5xl">
            Available for infrastructure work where correctness is the product.
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-ink-dim text-pretty">
            Autonomous agent systems, trading and execution rails, and the test discipline
            that makes them safe to run unattended.
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <Link
              href="/about/"
              className="border border-sapphire bg-sapphire px-6 py-3 font-mono text-[12px] tracking-[0.14em] text-void uppercase transition-colors hover:bg-transparent hover:text-sapphire"
            >
              Start a conversation
            </Link>
            <Link
              href="/architecture/"
              className="border border-line-lit px-6 py-3 font-mono text-[12px] tracking-[0.14em] text-ink-dim uppercase transition-colors hover:border-sapphire hover:text-ink"
            >
              See how it is built
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}

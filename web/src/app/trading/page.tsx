import type { Metadata } from 'next'
import {
  Eyebrow,
  PageHeader,
  Panel,
  Row,
  Rule,
  StatusChip,
  Terminal,
  Verified,
} from '@/components/Primitives'

export const metadata: Metadata = {
  title: 'Trading',
  description:
    'An inert design contract for bounded execution on designated rails. Runtime, broker, ' +
    'credential, and production availability are not claimed.',
  alternates: { canonical: '/trading/' },
}

const MODES = [
  {
    tone: 'ice' as const,
    label: 'Halted',
    body: 'Design state: a pause or hard safety veto leaves no order path open.',
  },
  {
    tone: 'degraded' as const,
    label: 'Off',
    body: 'Design state: observation or paper work carries no capital authority.',
  },
  {
    tone: 'sapphire' as const,
    label: 'Gated',
    body: 'Design state: a separately proven gate would still bind every real action.',
  },
  {
    tone: 'verified' as const,
    label: 'Free-reign',
    body:
      'Design state only: bounded autonomy requires current pause, broker, credential, ' +
      'runtime, and reconciliation evidence before it can exist.',
  },
]

const RAILS = [
  {
    term: 'RH Agentic MCP',
    body:
      'Proposed equities rail for the designated agentic account only. Option capability ' +
      'is not established; a separate bounded repair may add sell-to-close for one proven ' +
      'existing option, never an option purchase, roll, or exercise.',
  },
  {
    term: 'Free-reign easy',
    body:
      'Design intent: an independently armed policy could admit brokerage and designated ' +
      'L2 actions through the same ledger a human approval uses. Any such path remains ' +
      'unavailable until every required observation is separately proven current.',
  },
  {
    term: 'Account-scale envelopes',
    body:
      'The proposed verified, thesis, and L2 lanes would share bounded daily envelopes. ' +
      'This source description supplies no capital authority or current lane capacity.',
  },
  {
    term: 'Per-venue positions',
    body:
      'The design counts open-position limits per venue so brokerage and on-chain books ' +
      'would not share one ambiguous slot budget.',
  },
  {
    term: 'Kill switch',
    body:
      'The contract requires two canonical pause observations and fails closed on any ' +
      'missing, stale, unreadable, or unverifiable source.',
  },
  {
    term: 'Wallet fence',
    body:
      'The proposed executor would be restricted to designated addresses and the agentic ' +
      'brokerage account. This page establishes neither registry nor wallet availability.',
  },
]

const STACK = [
  {
    term: 'Super Heavy',
    body:
      'Primary planner (Grok high-effort) for plant orchestration. Plans only allowlisted ' +
      'tools — it never places orders. Local Nemotron is the offline fallback.',
  },
  {
    term: 'VPIN / TA / TV',
    body:
      'Flow-toxicity (VPIN), technical alerts, and TradingView webhooks feed proposals. ' +
      'Signals remain advisory and cannot establish current execution authority.',
  },
  {
    term: 'Windows plant',
    body:
      'The Windows GPU node is the intended executor host. Scheduled tasks, credentials, ' +
      'broker reconciliation, and production execution are currently unavailable.',
  },
]

export default function Trading() {
  return (
    <>
      <PageHeader
        eyebrow="Trading"
        title="A bounded execution design."
        lede="This page documents an inert contract. It does not establish that a broker, wallet, credential, runtime, pause source, or production execution path is currently available."
      />

      <section className="mx-auto max-w-6xl px-6 pt-10">
        <Panel>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <Eyebrow>Design contract</Eyebrow>
              <p className="mt-3 max-w-3xl text-sm leading-relaxed text-ink-dim">
                Task 063 source is merged but inert. Task 065, credential enrollment,
                broker reconciliation, runtime installation, and production execution
                remain unavailable until separately proven.
              </p>
            </div>
            <StatusChip tone="degraded">Runtime unavailable</StatusChip>
          </div>
          <p className="mt-5 text-sm text-ink">
            No control on this page can clear a pause, arm a gate, approve an action, or
            place an order.
          </p>
        </Panel>
      </section>

      <section className="mx-auto max-w-6xl px-6 pt-10">
        <div className="grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
          {MODES.map((mode) => (
            <div key={mode.label} className="bg-void px-5 py-5 md:px-6 md:py-6">
              <StatusChip tone={mode.tone}>{mode.label}</StatusChip>
              <p className="mt-4 text-sm leading-relaxed text-ink-dim text-pretty">{mode.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pt-16">
        <div className="grid gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
          <div>
            <Eyebrow>Order lifecycle</Eyebrow>
            <h2 className="mt-4 font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-4xl">
              Signal → free-reign → fill.
            </h2>
            <p className="mt-6 text-base leading-relaxed text-ink-dim">
              A signal is not an order. Research, VPIN, TA, and TV alerts become proposals.
              The proposed free-reign path could advance only after separately proven,
              current pause, gate, wallet, broker, and cap observations. Any unknown check
              stops the sequence. This diagram is not runtime telemetry.
            </p>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3">
              <Verified>Fail-closed by construction</Verified>
              <Verified>Designated agentic capital only</Verified>
            </div>
          </div>

          <Terminal
            title="design trace — runtime unavailable"
            scanline
            lines={[
              { prompt: true, text: 'desk propose --symbol HOOD --side buy --lane thesis' },
              { text: '' },
              { text: 'observe pause_sources    UNAVAILABLE', tone: 'dim' },
              { text: 'observe broker           UNAVAILABLE', tone: 'dim' },
              { text: 'observe credentials      UNAVAILABLE', tone: 'dim' },
              { text: 'observe runtime          UNAVAILABLE', tone: 'dim' },
              { text: '' },
              { text: '→ no action admitted', tone: 'dim' },
            ]}
          />
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="rails-heading">
        <Eyebrow>The rails</Eyebrow>
        <h2
          id="rails-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
        >
          Limits a strategy cannot argue with.
        </h2>
        <dl className="mt-12 border-t border-line">
          {RAILS.map((rail) => (
            <Row key={rail.term} term={rail.term} status={<StatusChip tone="ice">design</StatusChip>}>
              {rail.body}
            </Row>
          ))}
        </dl>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="stack-heading">
        <Eyebrow>Plant stack</Eyebrow>
        <h2
          id="stack-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
        >
          Orchestration without unsupervised authority.
        </h2>
        <dl className="mt-12 border-t border-line">
          {STACK.map((item) => (
            <Row key={item.term} term={item.term} status={<StatusChip tone="ice">documented</StatusChip>}>
              {item.body}
            </Row>
          ))}
        </dl>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6">
        <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
          <div>
            <Eyebrow>Scope</Eyebrow>
            <h2 className="mt-4 font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-4xl">
              What this desk is, and is not.
            </h2>
            <div className="mt-7 space-y-5 text-base leading-relaxed text-ink-dim">
              <p>
                It is a source-level design for bounded execution on designated test and
                agentic rails. The public site does not claim that those rails are installed,
                reconciled, enrolled, unpaused, or running.
              </p>
              <p>
                It is not a managed fund, it does not take outside capital, and nothing on
                this site is investment advice or an offer of any kind. Client and production
                money never share these rails.
              </p>
            </div>
          </div>

          <Panel>
            <p className="font-mono text-[11px] tracking-[0.16em] text-ink-faint uppercase">
              Disclosure
            </p>
            <div className="mt-5 space-y-4 text-sm leading-relaxed text-ink-dim">
              <p>
                Exact balances, current holdings, sizes, and live limits are excluded from
                anonymous responses. Public architecture telemetry is a separate contract
                and contains no capital state.
              </p>
              <p>
                Trading involves risk of loss. Past behaviour of any system described here
                does not indicate future results.
              </p>
              <p className="text-ink">
                Sapphire Alpha is not a registered investment adviser or broker-dealer.
              </p>
            </div>
          </Panel>
        </div>
      </section>
    </>
  )
}

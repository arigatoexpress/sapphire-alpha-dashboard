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
    'Robinhood Agentic free-reign strategy on designated rails — bounded by hard caps, ' +
    'wallet fences, Super Heavy orchestration, and a kill switch that fails closed.',
  alternates: { canonical: '/trading/' },
}

const MODES = [
  {
    tone: 'ice' as const,
    label: 'Halted',
    body: 'Kill switch present, or a hard safety veto. No order path is open.',
  },
  {
    tone: 'degraded' as const,
    label: 'Off',
    body: 'Desk is observing. Paper may run; nothing with real capital is proposed.',
  },
  {
    tone: 'sapphire' as const,
    label: 'Gated',
    body: 'Armed under caps. Every real action still waits for a human on the approval rail.',
  },
  {
    tone: 'verified' as const,
    label: 'Free-reign',
    body:
      'Armed agentic mode. Qualifying proposals on designated rails auto-approve under ' +
      'clip-to-cap limits — kill switch, wallet fence, and daily caps still bind.',
  },
]

const RAILS = [
  {
    term: 'RH Agentic MCP',
    body:
      'Brokerage execution for equities and single-leg options on the designated agentic ' +
      'account only. Crypto placement is split off the MCP path. Non-agentic accounts are ' +
      'rejected at the tool boundary.',
  },
  {
    term: 'Free-reign easy',
    body:
      'When armed, the policy layer auto-approves brokerage (and designated L2 tracks) ' +
      'through the same ledger a human approval uses. Account-scale envelopes — not ' +
      'toy ticket sizes. Oversized intent clips to the lane cap instead of bouncing.',
  },
  {
    term: 'Account-scale envelopes',
    body:
      'Verified / thesis / L2 lanes share a large daily envelope sized for the full ' +
      'agentic book. Hard stops remain kill switch + wallet fence only.',
  },
  {
    term: 'Per-venue positions',
    body:
      'Open-position limits are counted per venue so brokerage and on-chain books do not ' +
      'starve each other under a single global slot budget.',
  },
  {
    term: 'Kill switch',
    body:
      'A sentinel file on either host halts execution. Presence is checked before every ' +
      'action, and an unreadable check is treated as present.',
  },
  {
    term: 'Wallet fence',
    body:
      'Execution is restricted to a registry of designated addresses and the agentic ' +
      'brokerage account. A wallet not in the registry cannot be traded against.',
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
      'Signals are advisory until they pass the gate and free-reign or human approval.',
  },
  {
    term: 'Windows plant',
    body:
      'GPU executor hosts the schtasks plant: free-reign tick, executor consume, VPIN, ' +
      'orchestrator heartbeat. Mac remains control plane and RH MCP gate.',
  },
]

export default function Trading() {
  return (
    <>
      <PageHeader
        eyebrow="Trading"
        title="Agentic on designated rails."
        lede="The desk runs a Robinhood Agentic free-reign strategy on capital that is explicitly allowed to take risk. Every path to an order still passes through limits it cannot modify, and a switch a human can always throw."
      />

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
              Free-reign easy auto-approves only when the gate is armed, the kill switch is
              absent, the wallet is fenced, and the ticket fits (or clips into) the lane cap.
              Gated mode still waits for a human. Any check that cannot complete stops the
              sequence.
            </p>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3">
              <Verified>Fail-closed by construction</Verified>
              <Verified>Designated agentic capital only</Verified>
            </div>
          </div>

          <Terminal
            title="execution trace — free-reign easy · RH agentic"
            scanline
            lines={[
              { prompt: true, text: 'desk propose --symbol HOOD --side buy --lane thesis' },
              { text: '' },
              { text: 'check  wallet_fence      agentic_allowed', tone: 'verified' },
              { text: 'check  killswitch        absent', tone: 'verified' },
              { text: 'check  gate              ARMED', tone: 'verified' },
              { text: 'check  free_reign        easy · auto_approve', tone: 'verified' },
              { text: 'check  per_trade_cap     clip-to-cap', tone: 'sapphire' },
              { text: 'check  daily_cap         within limit', tone: 'verified' },
              { text: 'check  venue_slots       brokerage ok', tone: 'verified' },
              { text: '' },
              { text: '→ ledger auto-approve via free_reign', tone: 'verified' },
              { text: '→ executor consume → RH Agentic MCP', tone: 'dim' },
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
            <Row key={rail.term} term={rail.term} status={<Verified>enforced</Verified>}>
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
            <Row key={item.term} term={item.term} status={<Verified>live</Verified>}>
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
                It is an autonomous execution system running on designated test and agentic
                wallets — including a Robinhood Agentic brokerage account — with risk
                deliberately accepted on those envelopes.
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

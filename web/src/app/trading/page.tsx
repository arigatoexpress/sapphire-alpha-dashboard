import type { Metadata } from 'next'
import { Eyebrow, PageHeader, Panel, Row, Rule, Terminal, Verified } from '@/components/Primitives'

export const metadata: Metadata = {
  title: 'Trading',
  description:
    'Autonomous execution bounded by hard caps, a human approval rail, and a kill switch ' +
    'that fails closed. How the Sapphire Alpha desk is allowed to act.',
  alternates: { canonical: '/trading/' },
}

const RAILS = [
  {
    term: 'Per-trade cap',
    body:
      'Every order is checked against a hard notional ceiling before it is signed. The cap ' +
      'is configuration, not a constant in the strategy — a strategy cannot raise its own limit.',
  },
  {
    term: 'Daily cap',
    body:
      'Cumulative deployment is bounded per day. Once reached, the desk stops proposing ' +
      'rather than shrinking its orders to squeeze underneath.',
  },
  {
    term: 'Approval rail',
    body:
      'Proposals surface on a Telegram gate with the reasoning attached. Approve and deny ' +
      'are both one tap; no response is a deny.',
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
      'Execution is restricted to a registry of designated addresses. A wallet not in the ' +
      'registry cannot be traded against, regardless of what a strategy requests.',
  },
]

export default function Trading() {
  return (
    <>
      <PageHeader
        eyebrow="Trading"
        title="Bounded before it is fast."
        lede="The desk runs unattended. That is only defensible because every path to an order passes through limits it cannot modify, and a switch a human can always throw."
      />

      <section className="mx-auto max-w-6xl px-6 pt-14">
        <div className="grid gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
          <div>
            <Eyebrow>Order lifecycle</Eyebrow>
            <h2 className="mt-4 font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-4xl">
              Five checks between a signal and a fill.
            </h2>
            <p className="mt-6 text-base leading-relaxed text-ink-dim">
              A signal is not an order. It becomes one only after passing the wallet fence,
              both caps, the kill-switch check, and — depending on mode — a human. Any check
              that cannot complete stops the sequence.
            </p>
            <div className="mt-8">
              <Verified>Fail-closed by construction</Verified>
            </div>
          </div>

          <Terminal
            title="execution trace — designated test wallet"
            scanline
            lines={[
              { prompt: true, text: 'desk propose --symbol RTR --side buy' },
              { text: '' },
              { text: 'check  wallet_fence      registered', tone: 'verified' },
              { text: 'check  per_trade_cap     within limit', tone: 'verified' },
              { text: 'check  daily_cap         within limit', tone: 'verified' },
              { text: 'check  killswitch        absent', tone: 'verified' },
              { text: 'check  approval_rail     awaiting human', tone: 'sapphire' },
              { text: '' },
              { text: '→ proposal queued, not executed.', tone: 'dim' },
              { text: '  no response within window = deny.', tone: 'dim' },
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
                wallets, with risk deliberately accepted on those envelopes.
              </p>
              <p>
                It is not a managed fund, it does not take outside capital, and nothing on
                this site is investment advice or an offer of any kind.
              </p>
            </div>
          </div>

          <Panel>
            <p className="font-mono text-[11px] tracking-[0.16em] text-ink-faint uppercase">
              Disclosure
            </p>
            <div className="mt-5 space-y-4 text-sm leading-relaxed text-ink-dim">
              <p>
                Figures shown publicly are delayed and generalized. Exact balances, position
                sizes, and limits are operator-only and never appear in an anonymous response.
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

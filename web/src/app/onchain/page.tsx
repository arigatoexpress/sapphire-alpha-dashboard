import type { Metadata } from 'next'
import { Eyebrow, PageHeader, Panel, Row, Rule, Terminal, Verified } from '@/components/Primitives'
import { CHAIN } from '@/data/metrics'

export const metadata: Metadata = {
  title: 'On-Chain',
  description:
    `Settlement on ${CHAIN.name} (chain ${CHAIN.id}), an ${CHAIN.family}. A deliberately small ` +
    'contract surface, masked addresses, and off-chain logic that stays patchable.',
  alternates: { canonical: '/onchain/' },
}

const FACTS = [
  { term: 'Chain id', body: String(CHAIN.id) },
  { term: 'Network', body: CHAIN.name },
  { term: 'Family', body: CHAIN.family },
  { term: 'Contracts', body: '5 Solidity sources' },
  { term: 'Settlement', body: 'L2, batched to Ethereum' },
]

export default function OnChain() {
  return (
    <>
      <PageHeader
        eyebrow="On-Chain"
        title="The chain settles. It does not decide."
        lede={`Positions settle on ${CHAIN.name}, chain ${CHAIN.id}, an ${CHAIN.family}. Everything that requires judgement stays off-chain, where it can be tested and reverted.`}
      />

      <section className="mx-auto max-w-6xl px-6 pt-14">
        <div className="grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-5">
          {FACTS.map((fact, i) => (
            <div
              key={fact.term}
              className="rise bg-void p-6"
              style={{ animationDelay: `${i * 70}ms` }}
            >
              <p className="font-mono text-[11px] tracking-[0.16em] text-ink-faint uppercase">
                {fact.term}
              </p>
              <p className="tnum mt-3 font-display text-xl font-semibold text-ink">{fact.body}</p>
            </div>
          ))}
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6">
        <div className="grid gap-12 lg:grid-cols-[1fr_1fr] lg:gap-16">
          <div>
            <Eyebrow>Design</Eyebrow>
            <h2 className="mt-4 font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-4xl">
              Every deployed line is a line you cannot patch.
            </h2>
            <div className="mt-7 space-y-5 text-base leading-relaxed text-ink-dim">
              <p>
                That single constraint drives the whole on-chain design. Contracts hold
                custody and settlement — the parts that genuinely need to be trustless — and
                nothing else.
              </p>
              <p>
                Strategy, risk limits, and routing live off-chain in Python, where a mistake
                is a revert and a redeploy rather than a permanent liability. A larger
                on-chain surface would look more impressive and be considerably worse.
              </p>
            </div>
            <div className="mt-9 flex flex-wrap gap-x-6 gap-y-3">
              <Verified>Addresses masked in public</Verified>
              <Verified>Designated wallets only</Verified>
            </div>
          </div>

          <Terminal
            title={`chain ${CHAIN.id} — pinned in the suite`}
            lines={[
              { prompt: true, text: CHAIN.verify },
              { text: '' },
              { text: 'tests/test_rail_rh_l2.py:1', tone: 'dim' },
              { text: '  """Fund Factory T6/T10 — RH-L2 / RH-CHAIN' },
              { text: '  (chain 4663) on-chain rail goldens (TDD)."""', tone: 'sapphire' },
              { text: '' },
              { text: '# the chain id is not a constant in a slide.', tone: 'dim' },
              { text: '# it is an assertion the suite enforces.', tone: 'dim' },
            ]}
          />
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="privacy-heading">
        <Eyebrow>Privacy</Eyebrow>
        <h2
          id="privacy-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
        >
          Public chains are not anonymous. Plan accordingly.
        </h2>

        <dl className="mt-12 border-t border-line">
          <Row term="Masking" status={<Verified>enforced</Verified>}>
            Addresses are truncated to 0xabcd…1234 before they leave a process, and no wallet
            identifier — masked or otherwise — appears in an anonymous response.
          </Row>
          <Row term="Banding" status={<Verified>enforced</Verified>}>
            Public balance and deployment figures are rounded into bands. Exact values are
            operator-only, because an exact figure plus a public ledger is an identity.
          </Row>
          <Row term="Delay" status={<Verified>enforced</Verified>}>
            The public projection lags the operator view. Live position state is not a
            spectator sport, and a real-time feed is a front-running invitation.
          </Row>
          <Row term="Registry" status={<Verified>enforced</Verified>}>
            Only wallets in the designated registry can be traded against. The registry links
            a public address to a custody path — never to key material.
          </Row>
        </dl>

        <Panel className="mt-14">
          <p className="text-sm leading-relaxed text-ink-dim">
            <span className="text-ink">On the tension.</span> A site arguing for
            verifiability that also masks its addresses looks contradictory, and is not. What
            is verifiable is the <em>behaviour</em> of the system: the caps, the gates, the
            masking itself. What is withheld is the operator&rsquo;s position, which is
            information about a person rather than evidence about a system.
          </p>
        </Panel>
      </section>
    </>
  )
}

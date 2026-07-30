import { RH_CHAIN } from '@/data/mesh'
import { CORE_METRICS } from '@/data/metrics'

/**
 * The "proof of work" section. Three concrete things that the operator can
 * point at: the settlement rail with its chain id, the first mandate that has
 * cleared the gate, and the standing test claim about the codebase. Every
 * figure ships with the command that reproduces it — the same discipline that
 * keeps the numbers on this site honest.
 */

const TESTS = CORE_METRICS.find((m) => m.label === 'Test functions')!

const BRODIE = {
  name: 'BRODIE',
  amount: '$0.38',
  boundaries: [
    {
      label: 'Per-order cap',
      detail: 'Under $5 per proposal — an order that would spend more is refused before it leaves the machine.',
    },
    {
      label: 'Daily loss ceiling',
      detail: 'Realized loss above $25 in a day halts execution for the rest of the day.',
    },
    {
      label: 'Leverage floor',
      detail: 'Three times or less. Anything above rejects at the gate.',
    },
    {
      label: 'Human approval',
      detail: 'One Telegram tap authorizes exactly one order — no standing approvals, no batch clears.',
    },
  ],
  description:
    'The first mandate that arrived at the confirmation firewall, was scored by the ' +
    'policy shim, and cleared to execute. Small on purpose. The value of BRODIE is not ' +
    'the dollar amount; it is the four boundaries that had to hold for it to happen.',
} as const

export default function PortfolioProof() {
  return (
    <section id="proof" className="section proof" aria-labelledby="proof-title">
      <header className="section-head">
        <p className="section-kicker">04 · Proof</p>
        <h2 id="proof-title" className="section-title">
          A record, not a promise.<span>Every claim has a source.</span>
        </h2>
        <p className="section-lede">
          Anyone can build a beautiful dashboard. Fewer can point at one live
          settlement rail, one mandate that cleared four safety boundaries, and
          a test suite that keeps growing. These are the three things that make
          the rest of the site worth reading.
        </p>
      </header>

      <div className="proof-grid">
        <article className="proof-card proof-card--chain" aria-labelledby="proof-chain-title">
          <header>
            <p className="proof-card-kicker">Settlement rail</p>
            <h3 id="proof-chain-title">Robinhood Chain</h3>
          </header>
          <dl className="proof-card-facts">
            <div>
              <dt>Chain id</dt>
              <dd className="tnum">{RH_CHAIN.mainnet}</dd>
            </div>
            <div>
              <dt>Family</dt>
              <dd>{RH_CHAIN.family}</dd>
            </div>
            <div>
              <dt>Mainnet live</dt>
              <dd>{RH_CHAIN.liveSince}</dd>
            </div>
            <div>
              <dt>Testnet</dt>
              <dd className="tnum">{RH_CHAIN.testnet}</dd>
            </div>
          </dl>
          <p className="proof-card-body">
            Three contracts carry the surface —
            {' '}
            <code>{RH_CHAIN.contracts[0]}</code>,{' '}
            <code>{RH_CHAIN.contracts[1]}</code>, and{' '}
            <code>{RH_CHAIN.contracts[2]}</code>. Public wallet{' '}
            <code>{RH_CHAIN.publicWallet.slice(0, 6)}…{RH_CHAIN.publicWallet.slice(-4)}</code>;
            keys never enter this repo.
          </p>
        </article>

        <article className="proof-card proof-card--mandate" aria-labelledby="proof-brodie-title">
          <header>
            <p className="proof-card-kicker">First cleared mandate</p>
            <h3 id="proof-brodie-title">
              {BRODIE.name} · <span>{BRODIE.amount}</span>
            </h3>
          </header>
          <p className="proof-card-body">{BRODIE.description}</p>
          <ol className="proof-boundaries">
            {BRODIE.boundaries.map((b) => (
              <li key={b.label}>
                <strong>{b.label}</strong>
                <p>{b.detail}</p>
              </li>
            ))}
          </ol>
        </article>

        <article className="proof-card proof-card--tests" aria-labelledby="proof-tests-title">
          <header>
            <p className="proof-card-kicker">Verifiable coverage</p>
            <h3 id="proof-tests-title">Test surface</h3>
          </header>
          <p className="proof-card-figure tnum">{TESTS.value}</p>
          <p className="proof-card-caption">{TESTS.detail}</p>
          <details className="proof-verify">
            <summary>How to reproduce</summary>
            <pre>
              <code>{TESTS.verify}</code>
            </pre>
          </details>
        </article>
      </div>
    </section>
  )
}

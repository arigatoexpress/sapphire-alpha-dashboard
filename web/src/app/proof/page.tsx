import type { Metadata } from 'next'
import Link from 'next/link'
import { Eyebrow, PageHeader, Panel, Rule, Terminal, Verified } from '@/components/Primitives'

export const metadata: Metadata = {
  title: 'Proof ledger',
  description:
    'The control lifecycle, operating modes, failure behavior, public endpoints, and ' +
    'evidence boundaries behind Sapphire Alpha.',
  alternates: { canonical: '/proof/' },
}

const LIFECYCLE = [
  {
    n: '01',
    title: 'Observe',
    body: 'Collectors turn market, host, and chain state into typed snapshots. Missing data stays missing; it is never filled with a plausible number.',
    evidence: 'Freshness and source state appear in the live desk.',
  },
  {
    n: '02',
    title: 'Form intent',
    body: 'Research and models produce a proposal with a thesis, invalidation condition, horizon, and requested exposure.',
    evidence: 'Intent is data. It has no execution authority.',
  },
  {
    n: '03',
    title: 'Validate',
    body: 'Deterministic checks evaluate freshness, wallet scope, trade caps, daily caps, and the kill switch before any action can advance.',
    evidence: 'A missing or failed check resolves to stop.',
  },
  {
    n: '04',
    title: 'Authorize',
    body: 'The active operating mode decides whether a valid proposal needs explicit approval or may proceed inside a pre-authorized envelope.',
    evidence: 'Mode never expands the envelope; it only narrows authority.',
  },
  {
    n: '05',
    title: 'Execute',
    body: 'A separately provisioned worker translates the authorized intent into a bounded action. Models never receive private key material.',
    evidence: 'The edge cannot originate an execution.',
  },
  {
    n: '06',
    title: 'Reconcile',
    body: 'Receipts and resulting state are compared with the authorized intent. Divergence becomes an exception, not a rewritten story.',
    evidence: 'Decisions remain attributable to the rule and evidence in force.',
  },
] as const

const MODES = [
  {
    name: 'Observe',
    authority: 'None',
    description: 'Read, score, and record. No proposal may cross into execution.',
  },
  {
    name: 'Paper',
    authority: 'Simulated',
    description: 'Run the full lifecycle against a simulated fill and reconcile the hypothetical result.',
  },
  {
    name: 'Gated',
    authority: 'Per-action',
    description: 'A valid proposal pauses at authorization until an explicit approval arrives.',
  },
  {
    name: 'Free-reign (bounded autonomous)',
    authority: 'Pre-authorized envelope',
    description:
      'On designated RH Agentic and L2 rails only: free-reign easy auto-approves ' +
      'inside clip-to-cap, daily, and wallet fences. Mode never expands the envelope.',
  },
  {
    name: 'Paused',
    authority: 'Revoked',
    description: 'The kill switch wins over every model, queue, schedule, and previously valid proposal.',
  },
] as const

const FAILURES = [
  ['Telemetry stale', 'Proposal cannot validate', 'Wait for a fresh signed snapshot'],
  ['Signature invalid', 'Payload rejected', 'Rotate or repair the collector credential'],
  ['Replay detected', 'Sequence rejected', 'Advance the signed sequence and investigate'],
  ['Wallet outside scope', 'Execution blocked', 'No automatic remediation'],
  ['Capital cap breached', 'Execution blocked', 'Reduce intent or change the envelope out of band'],
  ['Approval missing', 'Proposal remains queued', 'Authorize explicitly or let it expire'],
  ['Kill switch active', 'All execution stops', 'A deliberate reset is required'],
  ['Receipt mismatch', 'Position is quarantined', 'Reconcile before another related action'],
] as const

const ENDPOINTS = [
  ['/api/health', 'Service liveness'],
  ['/api/build', 'Source, runtime revision, and shipped asset manifests'],
  ['/api/v1/live', 'Typed architecture telemetry used by the Evidence Horizon'],
  ['/api/v1/readiness', 'Exact inert-source and unavailable-runtime dependency state'],
  ['/api/v1/moss', 'Privacy-bounded on-chain observer state'],
  ['/api/v1/transparency', 'Capital and activity summaries with sensitive detail omitted'],
  ['/api/v1/status', 'Sanitized control-plane and service posture'],
  ['/api/v1/widgets', 'Compact, safe status projections for the live desk'],
  ['/api/fleet', 'Aggregate leases, gates, and snapshot age'],
  ['/api/v1/vault-map', 'A public-safe knowledge graph when a projection is available'],
] as const

const LEDGER = [
  {
    state: 'Shipped',
    tone: 'text-verified',
    title: 'Signed, replay-resistant telemetry',
    body: 'Ingest verifies the body signature, payload size, schema, and sequence before persistence. Anonymous callers receive a separate projection.',
  },
  {
    state: 'Source shipped',
    tone: 'text-ice',
    title: 'Fail-closed control contract',
    body: 'The source contract defaults to refusal. Runtime installation, credentials, broker reconciliation, and production execution remain unavailable until separately proven.',
  },
  {
    state: 'Shipped',
    tone: 'text-verified',
    title: 'Reproducible public measurements',
    body: 'Published counts identify what was counted, when it was counted, and the source revision. Nullable telemetry remains visibly unmeasured.',
  },
  {
    state: 'Withheld',
    tone: 'text-ice',
    title: 'Capital and identity detail',
    body: 'Exact balances, current holdings, wallet identifiers, hostnames, paths, prompts, and proposal bodies are absent from anonymous responses.',
  },
  {
    state: 'Not claimed',
    tone: 'text-ink-faint',
    title: 'No public performance claim',
    body: 'The site does not publish a return, hit rate, uptime percentage, or execution-latency figure until the underlying measurement is fit to inspect.',
  },
  {
    state: 'Not claimed',
    tone: 'text-ink-faint',
    title: 'No blanket security guarantee',
    body: 'Controls reduce defined failure modes. They do not make the system infallible, eliminate market risk, or replace independent review.',
  },
] as const

const GLOSSARY = [
  ['Intent', 'A structured request to act. It carries a thesis and limits, but no authority.'],
  [
    'Authority envelope',
    'The named wallets, instruments, actions, and capital limits an executor may not exceed.',
  ],
  [
    'Fail-closed',
    'A control posture where missing, stale, invalid, or uncertain input produces refusal.',
  ],
  [
    'Projection',
    'A deliberately smaller public view built from an internal record by an explicit whitelist.',
  ],
  ['Freshness', 'The measured age of an observation relative to the decision that depends on it.'],
  [
    'Reconciliation',
    'The comparison of authorized intent, execution receipt, and resulting state after an action.',
  ],
] as const

export default function Proof() {
  return (
    <>
      <PageHeader
        eyebrow="Proof ledger"
        title="A claim is only as strong as its failure path."
        lede="This is the contract beneath the interface: how evidence becomes intent, where authority stops, what the system does when a check fails, and which details never enter the public surface."
      />

      <section className="mx-auto max-w-6xl px-6 pt-14" aria-labelledby="lifecycle-heading">
        <div className="grid gap-10 lg:grid-cols-[0.72fr_1.28fr] lg:gap-20">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <Eyebrow>Control lifecycle</Eyebrow>
            <h2
              id="lifecycle-heading"
              className="mt-4 font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
            >
              Six gates from observation to record.
            </h2>
            <p className="mt-6 text-base leading-relaxed text-ink-dim">
              Intelligence may influence a proposal. It cannot erase a deterministic check,
              widen an authority envelope, or rewrite the receipt.
            </p>
          </div>

          <ol className="proof-spine">
            {LIFECYCLE.map((stage) => (
              <li key={stage.n} className="proof-step">
                <span className="proof-step__index">{stage.n}</span>
                <div>
                  <h3 className="font-display text-2xl font-semibold tracking-[-0.015em]">
                    {stage.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-dim">{stage.body}</p>
                  <p className="mt-4 font-mono text-[11px] leading-relaxed tracking-[0.04em] text-ice">
                    EVIDENCE · {stage.evidence}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="modes-heading">
        <Eyebrow>Authority</Eyebrow>
        <h2
          id="modes-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
        >
          Operating modes are permission ceilings.
        </h2>
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-ink-dim">
          A mode changes how far a valid intent may travel. It never changes whether the
          intent is valid. The active posture and freshness belong in the live desk, not in
          timeless marketing copy.
        </p>

        <ul className="mt-10 border-t border-line md:hidden">
          {MODES.map((mode) => (
            <li key={mode.name} className="border-b border-line py-6">
              <div className="flex items-baseline justify-between gap-5">
                <h3 className="font-display text-xl font-semibold">{mode.name}</h3>
                <p className="font-mono text-[10px] tracking-[0.08em] text-sapphire uppercase">
                  {mode.authority}
                </p>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-ink-dim">{mode.description}</p>
            </li>
          ))}
        </ul>

        <div className="mt-12 hidden border-y border-line md:block">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="font-mono text-[10px] tracking-[0.16em] text-ink-faint uppercase">
                <th className="py-4 pr-8 font-normal">Operating modes</th>
                <th className="px-8 py-4 font-normal">Authority</th>
                <th className="py-4 pl-8 font-normal">Behavior</th>
              </tr>
            </thead>
            <tbody>
              {MODES.map((mode) => (
                <tr key={mode.name} className="border-t border-line">
                  <th className="py-5 pr-8 font-display text-lg font-semibold">{mode.name}</th>
                  <td className="px-8 py-5 font-mono text-[12px] text-sapphire">{mode.authority}</td>
                  <td className="py-5 pl-8 text-sm leading-relaxed text-ink-dim">
                    {mode.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="failure-heading">
        <div className="grid gap-10 lg:grid-cols-[0.75fr_1.25fr] lg:gap-16">
          <div className="min-w-0">
            <Eyebrow>Failure matrix</Eyebrow>
            <h2
              id="failure-heading"
              className="mt-4 font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
            >
              Failure is a state, not a surprise.
            </h2>
            <p className="mt-6 text-base leading-relaxed text-ink-dim">
              Every important refusal should be legible: the condition, the immediate
              response, and the only safe way forward.
            </p>
          </div>

          <div className="border-t border-line">
            {FAILURES.map(([condition, response, recovery]) => (
              <div
                key={condition}
                className="grid gap-2 border-b border-line py-5 sm:grid-cols-[1fr_1fr] sm:gap-x-8"
              >
                <p className="font-mono text-[12px] tracking-[0.06em] text-ink uppercase">
                  {condition}
                </p>
                <p className="font-mono text-[11px] tracking-[0.08em] text-sapphire uppercase">
                  {response}
                </p>
                <p className="text-sm leading-relaxed text-ink-faint sm:col-start-2">{recovery}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="api-heading">
        <div className="grid gap-12 lg:grid-cols-[1fr_1fr] lg:gap-16">
          <div className="min-w-0">
            <Eyebrow>Public read surface</Eyebrow>
            <h2
              id="api-heading"
              className="mt-4 font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
            >
              Inspect the same projections the interface reads.
            </h2>
            <p className="mt-6 text-base leading-relaxed text-ink-dim">
              These are anonymous, read-only views. They expose state needed to understand
              the system while omitting exact capital, identity, key material, local paths,
              and executable authority.
            </p>

            <Terminal
              title="safe public reads"
              lines={[
                { prompt: true, text: 'curl -s https://sapphirealpha.xyz/api/health' },
                { text: '# service identity and readiness', tone: 'dim' },
                { text: '' },
                { prompt: true, text: 'curl -s https://sapphirealpha.xyz/api/v1/live' },
                { text: '# typed architecture telemetry; nullable means unmeasured', tone: 'dim' },
              ]}
            />
          </div>

          <dl className="min-w-0 border-t border-line">
            {ENDPOINTS.map(([path, description]) => (
              <div key={path} className="border-b border-line py-5">
                <dt>
                  <a
                    href={path}
                    className="font-mono text-[12px] text-sapphire underline decoration-line-lit underline-offset-4 transition-colors hover:text-ink"
                  >
                    GET {path}
                  </a>
                </dt>
                <dd className="mt-2 text-sm leading-relaxed text-ink-dim">{description}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="glossary-heading">
        <div className="grid gap-10 lg:grid-cols-[0.6fr_1.4fr] lg:gap-20">
          <div>
            <Eyebrow>Language contract</Eyebrow>
            <h2
              id="glossary-heading"
              className="mt-4 font-display text-3xl leading-tight font-semibold tracking-[-0.02em] md:text-4xl"
            >
              Working glossary.
            </h2>
            <p className="mt-5 text-sm leading-relaxed text-ink-dim">
              These words have operational meanings here. Precision matters most where a
              vague synonym could imply authority that does not exist.
            </p>
          </div>

          <dl className="grid gap-px border border-line bg-line sm:grid-cols-2">
            {GLOSSARY.map(([term, definition]) => (
              <div key={term} className="bg-void p-6">
                <dt className="font-mono text-[11px] tracking-[0.1em] text-ice uppercase">
                  {term}
                </dt>
                <dd className="mt-3 text-sm leading-relaxed text-ink-dim">{definition}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="ledger-heading">
        <div className="flex flex-wrap items-end justify-between gap-5">
          <div>
            <Eyebrow>Disclosure ledger</Eyebrow>
            <h2
              id="ledger-heading"
              className="mt-4 font-display text-3xl font-semibold tracking-[-0.02em] md:text-5xl"
            >
              What is true today.
            </h2>
          </div>
          <Verified>Scope stated</Verified>
        </div>

        <div className="mt-12 grid gap-px border border-line bg-line md:grid-cols-2">
          {LEDGER.map((entry) => (
            <article key={entry.title} className="bg-void p-7 md:p-9">
              <p className={`font-mono text-[10px] tracking-[0.18em] uppercase ${entry.tone}`}>
                {entry.state}
              </p>
              <h3 className="mt-5 font-display text-2xl font-semibold tracking-[-0.015em]">
                {entry.title}
              </h3>
              <p className="mt-4 text-sm leading-relaxed text-ink-dim">{entry.body}</p>
            </article>
          ))}
        </div>

        <Panel className="mt-12">
          <div className="flex flex-col items-start justify-between gap-7 md:flex-row md:items-center">
            <div>
              <p className="font-display text-2xl font-semibold">See the contract under load.</p>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-dim">
                The ledger explains the rules. The live desk shows their current inputs,
                freshness, and public-safe state.
              </p>
            </div>
            <Link
              href="/dashboard"
              className="shrink-0 border border-sapphire bg-sapphire px-5 py-3 font-mono text-[11px] tracking-[0.14em] text-void uppercase transition-colors hover:bg-transparent hover:text-sapphire"
            >
              Open live desk →
            </Link>
          </div>
        </Panel>
      </section>
    </>
  )
}

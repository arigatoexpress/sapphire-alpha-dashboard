import type { Metadata } from 'next'
import MetricCard from '@/components/Metric'
import { Eyebrow, PageHeader, Panel, Row, Rule, Terminal, Verified } from '@/components/Primitives'
import { DETAIL_METRICS, NODES } from '@/data/metrics'

export const metadata: Metadata = {
  title: 'Architecture',
  description:
    'Four nodes, one control plane, and a fail-closed gate between intent and execution. ' +
    'How the Sapphire Alpha stack is actually assembled.',
  alternates: { canonical: '/architecture/' },
}

const LAYERS = [
  {
    term: 'Control plane',
    body:
      'Orchestration, CI, and gate enforcement run on the Mac. It is the only machine ' +
      'permitted to approve an outward action, and it holds no execution keys.',
  },
  {
    term: 'Execution',
    body:
      'A Windows GPU node runs inference, free-reign policy ticks, and order placement. ' +
      'Robinhood Agentic MCP handles the brokerage rail; on-chain uses provisioned wallets. ' +
      'Both act only inside caps and designated envelopes.',
  },
  {
    term: 'Orchestration',
    body:
      'Grok Super Heavy is the primary plant planner (high effort); local Nemotron is the ' +
      'offline fallback. Orchestrators propose and schedule — they never hold keys or place.',
  },
  {
    term: 'Telemetry',
    body:
      'Collectors on both machines emit HMAC-signed semantic snapshots. The edge validates ' +
      'the signature, rejects replays, and persists to Firestore.',
  },
  {
    term: 'Public edge',
    body:
      'Cloud Run serves this site, the architecture telemetry API, and separate ' +
      'privacy-bounded capital summaries. It is the only internet-reachable surface, ' +
      'and it can read nothing it was not pushed.',
  },
]

export default function Architecture() {
  return (
    <>
      <PageHeader
        eyebrow="Architecture"
        title="Four machines that do not trust each other."
        lede="Separation is the design. The node that decides is not the node that executes, and the node the public can reach holds nothing it was not explicitly handed."
      />

      <section className="mx-auto max-w-6xl px-6 pt-14">
        <div className="grid gap-px border border-line bg-line md:grid-cols-2">
          {NODES.map((node, i) => (
            <div
              key={node.id}
              className="rise bg-void p-7 md:p-9"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div className="flex items-baseline justify-between gap-4">
                <h2 className="font-display text-2xl font-semibold tracking-[-0.015em]">
                  {node.role}
                </h2>
                <span className="font-mono text-[11px] tracking-[0.16em] text-sapphire uppercase">
                  {node.id}
                </span>
              </div>
              <p className="mt-2 font-mono text-[12px] text-ink-faint">{node.hardware}</p>
              <p className="mt-5 text-sm leading-relaxed text-ink-dim">{node.duty}</p>
            </div>
          ))}
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="layers-heading">
        <Eyebrow>Request path</Eyebrow>
        <h2
          id="layers-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
        >
          Intent travels one direction. Authority never does.
        </h2>

        <dl className="mt-12 border-t border-line">
          {LAYERS.map((layer) => (
            <Row key={layer.term} term={layer.term}>
              {layer.body}
            </Row>
          ))}
        </dl>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6">
        <div className="grid gap-12 lg:grid-cols-[1fr_1fr] lg:gap-16">
          <div>
            <Eyebrow>The stack</Eyebrow>
            <h2 className="mt-4 font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-4xl">
              Boring technology, deliberately.
            </h2>
            <div className="mt-7 space-y-5 text-base leading-relaxed text-ink-dim">
              <p>
                FastAPI and Python on the backend. React on the operator dashboard, statically
                exported Next.js for this site. Firestore for telemetry, Cloud Run for the
                edge, Tailscale for the mesh between machines.
              </p>
              <p>
                None of that is interesting, which is the point. The novelty budget is spent
                on the safety model and the test suite, not on the framework list.
              </p>
            </div>

            <div className="mt-9 flex flex-wrap gap-x-6 gap-y-3">
              <Verified>Single container</Verified>
              <Verified>One deploy path</Verified>
              <Verified>No runtime secrets in image</Verified>
            </div>
          </div>

          <Terminal
            title="deploy path"
            lines={[
              { text: '# one image, one service, one domain.', tone: 'dim' },
              { text: '' },
              {
                prompt: true,
                text: './deploy.sh',
              },
              { text: 'step 0: verify source ................. ok', tone: 'verified' },
              { text: 'step 1: docker build  ................. ok', tone: 'verified' },
              { text: 'step 2: docker push   ................. ok', tone: 'verified' },
              { text: 'step 3: run deploy    ................. ok', tone: 'verified' },
              { text: '' },
              { text: 'service   sapphire-alpha-dashboard' },
              { text: 'region    us-central1' },
              { text: 'image     immutable build ID', tone: 'sapphire' },
              { text: '' },
              { text: '# secrets resolve at runtime, never baked in.', tone: 'dim' },
            ]}
          />
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6">
        <Eyebrow>Scale</Eyebrow>
        <h2 className="mt-4 font-display text-3xl font-semibold tracking-[-0.02em] md:text-4xl">
          Surface area, counted.
        </h2>
        <div className="mt-12 grid gap-x-10 gap-y-14 sm:grid-cols-2 lg:grid-cols-3">
          {DETAIL_METRICS.map((metric, i) => (
            <MetricCard key={metric.label} metric={metric} index={i} />
          ))}
        </div>

        <Panel className="mt-14">
          <p className="text-sm leading-relaxed text-ink-dim">
            <span className="text-ink">A note on the Solidity count.</span> Five contracts is
            a small on-chain surface, and that is intentional: every line deployed to a chain
            is a line that cannot be patched. Logic lives off-chain where it can be tested,
            reverted, and re-deployed in minutes. The chain settles; it does not decide.
          </p>
        </Panel>
      </section>
    </>
  )
}

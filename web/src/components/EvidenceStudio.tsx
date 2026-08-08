import Link from 'next/link'
import LiveTruthRail from '@/components/LiveTruthRail'
import { FEATURED_OBSERVATION as observation } from '@/data/metrics'

const blockStart = Number(observation.range.startBlock)
const blockEnd = Number(observation.range.endBlock)
const BLOCKS = Array.from(
  { length: blockEnd - blockStart + 1 },
  (_unused, index) => String(blockStart + index),
)

export default function EvidenceStudio() {
  return (
    <div className="evidence-studio">
      <section className="studio-hero" aria-labelledby="studio-title">
        <div className="studio-hero__copy">
          <p className="studio-eyebrow">Sapphire Alpha · Evidence intelligence</p>
          <h1 id="studio-title">Markets are noisy. The evidence shouldn’t be.</h1>
          <p className="studio-lede">
            An agent-native research studio for market structure, onchain activity, and
            falsifiable decisions. Every visual identifies its source class, observation time,
            invalidation condition, and authority boundary.
          </p>
          <div className="studio-actions">
            <Link href="/dashboard" className="studio-action studio-action--primary">
              Open the live desk
            </Link>
            <Link href="/research/research-methodology/" className="studio-action">
              Inspect the method
            </Link>
          </div>
          <dl className="studio-promise" aria-label="Product boundaries">
            <div>
              <dt>Source</dt>
              <dd>Named and inspectable</dd>
            </div>
            <div>
              <dt>Freshness</dt>
              <dd>Never inferred</dd>
            </div>
            <div>
              <dt>Authority</dt>
              <dd>Explicitly bounded</dd>
            </div>
          </dl>
        </div>
        <LiveTruthRail />
      </section>

      <section className="evidence-dossier" aria-labelledby="dossier-title">
        <header className="dossier-header">
          <div>
            <p className="studio-eyebrow">Featured evidence dossier · onchain</p>
            <h2 id="dossier-title">{observation.assetPair}</h2>
          </div>
          <div className="dossier-status">
            <span>Observation, not signal</span>
            <strong>{observation.finality.outcome}</strong>
            <small>{observation.finality.limitation}</small>
          </div>
        </header>

        <div className="dossier-grid">
          <figure className="block-observation">
            <figcaption>
              <div>
                <span>Exact block window</span>
                <strong>
                  {observation.range.startBlock} → {observation.range.endBlock}
                </strong>
              </div>
              <div>
                <span>Admitted events</span>
                <strong>{observation.eventCount}</strong>
              </div>
            </figcaption>
            <div
              className="block-track"
              aria-label={`${BLOCKS.length}-block observation window`}
            >
              {BLOCKS.map((block, index) => (
                <div className="block-tick" data-event={index === BLOCKS.length - 1} key={block}>
                  <i aria-hidden="true" />
                  <span>{block.slice(-3)}</span>
                  {index === BLOCKS.length - 1 ? <b>{observation.eventType}</b> : null}
                </div>
              ))}
            </div>
            <p>
              One canonical event was admitted across {observation.validatedPools} identity-checked
              pools. Counts describe this window only; they are not market-wide activity.
            </p>
          </figure>

          <aside className="dossier-ledger" aria-label="Evidence ledger">
            <dl>
              <div>
                <dt>Chain</dt>
                <dd>{observation.chain} · {observation.chainId}</dd>
              </div>
              <div>
                <dt>Observed</dt>
                <dd>{observation.observedAt}</dd>
              </div>
              <div>
                <dt>Batch receipt</dt>
                <dd>{observation.receiptSha256.slice(0, 12)}…</dd>
              </div>
              <div>
                <dt>Limit</dt>
                <dd>No volume, ranking, finality, or trading authority</dd>
              </div>
            </dl>
            <a href={observation.sourceUrl}>Official network definition ↗</a>
            <Link href={observation.methodUrl}>Inspect the public research method ↗</Link>
            <details>
              <summary>Verify projection integrity</summary>
              <code>{observation.verify}</code>
            </details>
            <p className="dossier-disclaimer">
              The complete receipts remain owner-only; this is a content-addressed,
              privacy-safe projection. Not investment advice. This public surface cannot
              trade, approve, or clear a policy boundary.
            </p>
          </aside>
        </div>
      </section>

      <section className="studio-method" aria-labelledby="method-title">
        <header>
          <p className="studio-eyebrow">Agent-enhanced, evidence constrained</p>
          <h2 id="method-title">A chart should explain what it knows.</h2>
          <p>
            Sapphire’s job is not to decorate a price series. It is to join market data,
            onchain state, research context, and explicit uncertainty into one inspectable record.
          </p>
        </header>
        <ol>
          <li>
            <span>01</span>
            <strong>Observe</strong>
            <p>Capture immutable source bytes at one declared time or block.</p>
          </li>
          <li>
            <span>02</span>
            <strong>Cross-check</strong>
            <p>Resolve identity, continuity, provenance, and independent corroboration.</p>
          </li>
          <li>
            <span>03</span>
            <strong>Explain</strong>
            <p>Separate the observation, interpretation, alternative, and falsifier.</p>
          </li>
          <li>
            <span>04</span>
            <strong>Gate</strong>
            <p>Research can propose. A separate policy boundary owns every consequential action.</p>
          </li>
        </ol>
      </section>
    </div>
  )
}

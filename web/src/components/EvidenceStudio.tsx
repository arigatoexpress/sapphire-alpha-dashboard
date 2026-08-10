import Link from 'next/link'
import LiveTruthRail from '@/components/LiveTruthRail'
import { FEATURED_OBSERVATION as observation } from '@/data/metrics'

const blockStart = Number(observation.range.startBlock)
const blockEnd = Number(observation.range.endBlock)
const BLOCKS = Array.from(
  { length: blockEnd - blockStart + 1 },
  (_unused, index) => String(blockStart + index),
)

const PROGRAMS = [
  {
    index: '01',
    chain: 'Robinhood Chain',
    status: 'Receipt-backed pilot',
    state: 'observed',
    copy: 'Tokenized-equity pool identity and canonical event evidence, constrained to declared block windows.',
    foot: 'Admitted specimen · AAPL / USDG',
  },
  {
    index: '02',
    chain: 'MegaETH',
    status: 'Discovery — no admitted feed',
    state: 'discovery',
    copy: 'MNSTR and tokenized-collectibles research is being mapped. No runtime coverage is claimed here yet.',
    foot: 'Research surface · pre-ingest',
  },
  {
    index: '03',
    chain: 'Solana',
    status: 'Connector planned',
    state: 'planned',
    copy: 'A mobile-first intelligence route is in the roadmap. It remains separate from trading authority.',
    foot: 'Architecture lane · not live',
  },
] as const

function IntelligenceField() {
  return (
    <figure
      className="intelligence-field"
      data-signature="intelligence-field"
      aria-label="Sapphire intelligence field"
    >
      <figcaption>
        <span>System topology</span>
        <strong>Sovereign loop / public projection</strong>
      </figcaption>
      <div className="field-stage" aria-hidden="true">
        <div className="field-axis field-axis--x" />
        <div className="field-axis field-axis--y" />
        <div className="field-orbit field-orbit--outer" />
        <div className="field-orbit field-orbit--inner" />
        <div className="field-core">
          <span>S</span>
          <small>Sapphire</small>
        </div>
        <span className="field-node field-node--market">Markets</span>
        <span className="field-node field-node--chain">Onchain</span>
        <span className="field-node field-node--memory">Memory</span>
        <span className="field-node field-node--policy">Policy</span>
        <i className="field-pulse field-pulse--one" />
        <i className="field-pulse field-pulse--two" />
      </div>
      <ol className="field-loop" aria-label="Intelligence loop">
        {['Observe', 'Reason', 'Decide', 'Act'].map((stage, index) => (
          <li key={stage}>
            <span>{String(index + 1).padStart(2, '0')}</span>
            {stage}
          </li>
        ))}
      </ol>
      <p>Actions remain outside the public surface and behind an explicit policy gate.</p>
    </figure>
  )
}

export default function EvidenceStudio() {
  return (
    <div className="sovereign-home">
      <section className="sovereign-hero" aria-labelledby="sovereign-title">
        <div className="sovereign-hero__copy">
          <p className="lab-kicker"><span /> A sovereign market laboratory</p>
          <h1 id="sovereign-title">
            <span>Find the signal.</span>
            <em>Prove the path.</em>
          </h1>
          <p className="sovereign-hero__lede">
            Sapphire connects market structure, onchain state, durable memory, and
            autonomous research—then shows exactly where evidence ends and judgment begins.
          </p>
          <div className="sovereign-actions">
            <Link href="/dashboard" className="sovereign-action sovereign-action--primary">
              Enter mission control <span aria-hidden="true">↗</span>
            </Link>
            <Link href="/architecture/" className="sovereign-action">
              Read the operating thesis <span aria-hidden="true">→</span>
            </Link>
          </div>
          <dl className="sovereign-contract" aria-label="Public evidence contract">
            <div><dt>Source</dt><dd>Named</dd></div>
            <div><dt>Freshness</dt><dd>Declared</dd></div>
            <div><dt>Falsifier</dt><dd>Required</dd></div>
            <div><dt>Authority</dt><dd>Bounded</dd></div>
          </dl>
        </div>
        <IntelligenceField />
      </section>

      <div className="lab-ticker" aria-label="Research domains">
        <span>Market intelligence</span><i />
        <span>Onchain fundamentals</span><i />
        <span>Agent operations</span><i />
        <span>Decision provenance</span><i />
        <span>Tokenized collectibles</span><i />
        <span>Ethereum + Hyperliquid research</span>
      </div>

      <section className="programs" aria-labelledby="programs-title">
        <header className="section-intro">
          <p className="lab-kicker"><span /> Active research surface</p>
          <h2 id="programs-title">Built across markets.<br />Honest about the edges.</h2>
          <p>
            Coverage is a claim. Every program below says what has been observed,
            what is still being built, and what the public site cannot do.
          </p>
        </header>
        <div className="program-grid">
          {PROGRAMS.map((program) => (
            <article key={program.chain} className="program-card" data-state={program.state}>
              <div className="program-card__head">
                <span>{program.index}</span>
                <small>{program.status}</small>
              </div>
              <h3>{program.chain}</h3>
              <p>{program.copy}</p>
              <footer>{program.foot}</footer>
            </article>
          ))}
        </div>
      </section>

      <section className="runtime-proof" aria-labelledby="runtime-title">
        <div className="runtime-proof__copy">
          <p className="lab-kicker"><span /> Runtime truth</p>
          <h2 id="runtime-title">The interface refuses to guess.</h2>
          <p>
            A missing feed stays missing. A stale observation stays stale. Runtime state is
            projected from its admitted source; page-load time never launders old data into “live.”
          </p>
          <Link href="/proof/">Inspect the evidence protocol →</Link>
        </div>
        <LiveTruthRail />
      </section>

      <section className="evidence-exhibit" aria-labelledby="exhibit-title">
        <header className="exhibit-header">
          <div>
            <p className="lab-kicker"><span /> Featured evidence dossier · public specimen</p>
            <h2 id="exhibit-title">{observation.assetPair}</h2>
          </div>
          <div className="exhibit-verdict">
            <span>Observation, not signal</span>
            <strong>{observation.finality.outcome}</strong>
            <small>{observation.finality.limitation}</small>
          </div>
        </header>

        <div className="exhibit-grid">
          <figure className="block-observation">
            <figcaption>
              <div><span>Exact block window</span><strong>{observation.range.startBlock} → {observation.range.endBlock}</strong></div>
              <div><span>Admitted events</span><strong>{observation.eventCount}</strong></div>
            </figcaption>
            <div className="block-track" aria-label={`${BLOCKS.length}-block observation window`}>
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

          <aside className="exhibit-ledger" aria-label="Evidence ledger">
            <dl>
              <div><dt>Chain</dt><dd>{observation.chain} · {observation.chainId}</dd></div>
              <div><dt>Observed</dt><dd>{observation.observedAt}</dd></div>
              <div><dt>Receipt</dt><dd>{observation.receiptSha256.slice(0, 12)}…</dd></div>
              <div><dt>Limit</dt><dd>No volume, ranking, finality, or trading authority</dd></div>
            </dl>
            <details>
              <summary>Verify projection integrity</summary>
              <code>{observation.verify}</code>
            </details>
            <a href={observation.sourceUrl}>Official network definition ↗</a>
            <Link href={observation.methodUrl}>Read the public method →</Link>
          </aside>
        </div>
      </section>

      <section className="operating-loop" aria-labelledby="loop-title">
        <header>
          <p className="lab-kicker"><span /> Intelligence with receipts</p>
          <h2 id="loop-title">One loop. Four hard contracts.</h2>
        </header>
        <ol>
          <li><span>Observe</span><p>Capture immutable source bytes at a declared time or block.</p></li>
          <li><span>Cross-check</span><p>Resolve identity, continuity, and independent corroboration.</p></li>
          <li><span>Explain</span><p>Separate evidence, interpretation, alternatives, and uncertainty.</p></li>
          <li><span>Gate</span><p>Score the thesis, then route consequential actions through policy.</p></li>
        </ol>
        <p className="operating-loop__disclosure">
          This public surface cannot trade. Not investment advice. It exposes
          evidence and limits; private policy owns any consequential action.
        </p>
      </section>
    </div>
  )
}

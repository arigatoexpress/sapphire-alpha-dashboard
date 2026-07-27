/** Shared visual explainer primitives — probability rings, path bands, method flow. */

export function ProbabilityRing({
  p,
  label,
  sub,
  size = 148,
}: {
  p: number
  label: string
  sub?: string
  size?: number
}) {
  const pct = Math.round(Math.max(0, Math.min(1, p)) * 100)
  const r = 54
  const c = 2 * Math.PI * r
  const dash = (pct / 100) * c
  return (
    <div className="viz-ring" style={{ width: size }}>
      <svg viewBox="0 0 128 128" width={size} height={size} aria-hidden="true">
        <circle cx="64" cy="64" r={r} className="viz-ring-track" />
        <circle
          cx="64"
          cy="64"
          r={r}
          className="viz-ring-fill"
          strokeDasharray={`${dash} ${c - dash}`}
          transform="rotate(-90 64 64)"
        />
        <text x="64" y="60" textAnchor="middle" className="viz-ring-num">
          {pct}%
        </text>
        <text x="64" y="78" textAnchor="middle" className="viz-ring-unit">
          point estimate
        </text>
      </svg>
      <strong>{label}</strong>
      {sub ? <span>{sub}</span> : null}
    </div>
  )
}

export function PathBandChart({
  spot,
  bear,
  base,
  bull,
  asset = 'BTC',
  horizon = '90d path',
}: {
  spot: number
  bear: number
  base: number
  bull: number
  asset?: string
  horizon?: string
}) {
  const lo = Math.min(bear, base, bull, spot) * 0.96
  const hi = Math.max(bear, base, bull, spot) * 1.04
  const x = (v: number) => ((v - lo) / (hi - lo)) * 100
  return (
    <div className="viz-path">
      <div className="viz-path-head">
        <strong>
          {asset} · {horizon}
        </strong>
        <span>bear / base / bull — not event odds</span>
      </div>
      <div className="viz-path-track" aria-hidden="true">
        <i className="viz-path-band" style={{ left: `${x(bear)}%`, width: `${x(bull) - x(bear)}%` }} />
        <b className="viz-path-spot" style={{ left: `${x(spot)}%` }} title={`spot ${spot}`} />
        <em style={{ left: `${x(bear)}%` }} data-label="bear" />
        <em style={{ left: `${x(base)}%` }} data-label="base" />
        <em style={{ left: `${x(bull)}%` }} data-label="bull" />
      </div>
      <div className="viz-path-scale">
        <span>${bear.toLocaleString()}</span>
        <span className="mid">spot ${spot.toLocaleString()}</span>
        <span>${bull.toLocaleString()}</span>
      </div>
    </div>
  )
}

export function MethodFlow() {
  const steps = [
    { n: '01', t: 'Observe', d: 'Public market data' },
    { n: '02', t: 'Event P', d: 'One number as-of now' },
    { n: '03', t: 'Path', d: 'S / M / L targets' },
    { n: '04', t: 'Score', d: 'Brier · path hit-rate' },
    { n: '05', t: 'Learn', d: 'Priors · lessons · notes' },
    { n: '06', t: 'Act', d: 'Gated designated rails' },
  ]
  return (
    <ol className="viz-flow" aria-label="Research method">
      {steps.map((s, i) => (
        <li key={s.n}>
          <span>{s.n}</span>
          <strong>{s.t}</strong>
          <p>{s.d}</p>
          {i < steps.length - 1 ? <i aria-hidden="true" /> : null}
        </li>
      ))}
    </ol>
  )
}

export function ConceptCards() {
  return (
    <div className="viz-concepts">
      <article>
        <div className="viz-concepts-icon" aria-hidden="true">
          <svg viewBox="0 0 48 48">
            <circle cx="24" cy="24" r="18" fill="none" stroke="currentColor" strokeWidth="1.5" />
            <path d="M24 6a18 18 0 0 1 0 36" fill="currentColor" opacity="0.35" />
            <text x="24" y="28" textAnchor="middle" fontSize="11" fill="currentColor" fontFamily="monospace">
              P
            </text>
          </svg>
        </div>
        <h3>Event probability</h3>
        <p>
          “Has Bitcoin bottomed?” gets <em>one</em> probability at the timestamp we form it. Not
          short, medium, and long versions of the same question.
        </p>
      </article>
      <article>
        <div className="viz-concepts-icon" aria-hidden="true">
          <svg viewBox="0 0 48 48">
            <path
              d="M6 34 L16 28 L26 30 L42 12"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
            />
            <path d="M6 38 H42" stroke="currentColor" strokeWidth="1" opacity="0.35" />
            <rect x="14" y="18" width="20" height="10" fill="currentColor" opacity="0.2" />
          </svg>
        </div>
        <h3>Path bands</h3>
        <p>
          Short / medium / long are for <em>where price might go</em> — bear, base, and bull
          scenarios with weights. Growth and trends live here.
        </p>
      </article>
      <article>
        <div className="viz-concepts-icon" aria-hidden="true">
          <svg viewBox="0 0 48 48">
            <path
              d="M10 34 L24 10 L38 34 Z"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <path d="M24 18 V28 M24 32 V34" stroke="currentColor" strokeWidth="2" />
          </svg>
        </div>
        <h3>Falsifier first</h3>
        <p>
          Every claim writes what would prove it wrong <em>before</em> the outcome. We score
          later so opinions stay honest — not just narrative.
        </p>
      </article>
    </div>
  )
}

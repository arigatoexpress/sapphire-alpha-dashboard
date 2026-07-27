import { PUBLIC_DOCTRINE } from '@shared/doctrine'
import { formatCount, formatRate } from '../desk/format'
import type { LiveSnapshot } from '../types'

export function MarketAperture({ snapshot }: { snapshot: LiveSnapshot | null }) {
  const { posture, primary, lenses, inputCap, evidenceMinimum } = PUBLIC_DOCTRINE

  return (
    <section
      id="doctrine"
      data-market-aperture="true"
      aria-labelledby="aperture-title"
      className="market-aperture rise scroll-mt-24"
    >
      <div className="aperture-copy">
        <p className="aperture-kicker">Live desk · designated rails only</p>
        <h1 id="aperture-title">Plant status</h1>
        <p className="aperture-lede">
          Real execution posture, risk runway, and decision queue. No paper
          backtest leaderboards. Research opinions live on the public research
          pages with a single event probability and separate path bands.
        </p>

        <div className="aperture-contract">
          <div>
            <span>Current posture</span>
            <strong>{posture}</strong>
          </div>
          <div>
            <span>Primary cycle lens</span>
            <strong>{primary.name} · {primary.scope}</strong>
          </div>
        </div>

        <div className="aperture-boundary">
          <strong>Evidence, not authority</strong>
          <span>{evidenceMinimum} independent checks · {inputCap} max per input</span>
        </div>
      </div>

      <div className="aperture-visual" aria-label="Research authority map">
        <div className="optic" aria-hidden="true">
          <div className="optic-halo" />
          <div className="optic-ring optic-ring-outer" />
          <div className="optic-ring optic-ring-primary" />
          <div className="optic-crosshair" />
          <div className="optic-core">
            <span>Mandate</span>
            <strong>Private</strong>
            <small>sets conviction</small>
          </div>
        </div>

        <div className="optic-primary">
          <span>Primary cycle</span>
          <strong>{primary.name}</strong>
        </div>

        <div className="optic-advisers">
          {lenses.map((lens) => (
            <div key={lens.name}>
              <strong>{lens.name}</strong>
              <span>{lens.scope}</span>
            </div>
          ))}
        </div>

        <p className="optic-boundary">Execution stays outside this lens</p>
      </div>

      <div className="aperture-telemetry" aria-label="Current system summary">
        <div>
          <span>Task agents active</span>
          <strong>{formatCount(snapshot?.summary.active_agents)}</strong>
        </div>
        <div>
          <span>Events / min</span>
          <strong>{formatRate(snapshot?.summary.events_per_min)}</strong>
        </div>
        <div>
          <span>Verified today</span>
          <strong>{formatCount(snapshot?.summary.verified_today)}</strong>
        </div>
        <div>
          <span>Human gates</span>
          <strong>{formatCount(snapshot?.summary.attention)}</strong>
        </div>
      </div>
    </section>
  )
}

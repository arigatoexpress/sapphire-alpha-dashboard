import type { LiveDesk } from '../types'
import {
  executionTone,
  formatExecution,
  formatNewRisk,
  formatPercent,
  formatPosture,
  formatRatio,
  NOT_OBSERVED,
  riskTone,
} from '../desk/format'

function ModeChip({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone: 'ice' | 'sapphire' | 'degraded' | 'failed' | 'neutral'
}) {
  return (
    <div className={`mode-chip mode-chip--${tone}`}>
      <span>{label}</span>
      <strong className="tnum">{value}</strong>
    </div>
  )
}

/**
 * Live desk cockpit — real plant state only.
 * Paper backtest tracks, OOS sealed-trial theater, and replay-conflict
 * scoreboards are intentionally gone. What remains is execution posture,
 * risk runway, decision queue, and the two designated rails.
 */
export function DecisionCockpit({ desk }: { desk: LiveDesk | null }) {
  const used = desk?.risk?.realized_drawdown_pct
  const limit = desk?.risk?.drawdown_limit_pct
  const runwayFill =
    used !== null && used !== undefined && limit
      ? Math.min(100, Math.max(0, (used * 100) / limit))
      : 0
  const runwayCritical = runwayFill >= 90
  const runwayElevated = runwayFill >= 70
  const execTone = executionTone(desk?.execution)
  const newRiskTone = riskTone(desk?.risk?.new_risk)

  const gates = [
    {
      label: 'Market data',
      value: desk ? formatRatio(desk.feeds.fresh, desk.feeds.total, ' fresh') : NOT_OBSERVED,
      state: desk && desk.feeds.fresh === desk.feeds.total ? 'pass' : 'hold',
    },
    {
      label: 'Loss ledger',
      value: desk?.risk?.ledger_state === 'reconciled' ? 'Reconciled' : NOT_OBSERVED,
      state: desk?.risk?.ledger_state === 'reconciled' ? 'pass' : 'hold',
    },
    {
      label: 'Order runway',
      value: formatNewRisk(desk?.risk?.new_risk),
      state: desk?.risk?.new_risk === 'available' ? 'pass' : 'hold',
    },
    {
      label: 'Execution',
      value: formatExecution(desk?.execution),
      state: desk?.execution === 'gated' ? 'pass' : 'hold',
    },
  ] as const

  const queue = [
    { label: 'Awaiting review', value: desk?.decisions.pending_review ?? NOT_OBSERVED },
    {
      label: 'Blocked by policy',
      value: desk?.decisions.pending_policy_blocked ?? NOT_OBSERVED,
    },
    {
      label: 'Approved · waiting',
      value: desk?.decisions.approved_awaiting_execution ?? NOT_OBSERVED,
    },
    { label: 'Eligible to fire', value: desk?.decisions.eligible_execution ?? NOT_OBSERVED },
    {
      label: 'Blocked after approve',
      value: desk?.decisions.blocked ?? NOT_OBSERVED,
      blocked: (desk?.decisions.blocked ?? 0) > 0,
    },
    {
      label: 'Execution mode',
      value: formatExecution(desk?.execution),
      protected: desk?.execution === 'halted' || desk?.execution === 'off',
      gated: desk?.execution === 'gated',
    },
  ]

  return (
    <section
      id="decisions"
      aria-labelledby="decision-title"
      className="decision-cockpit scroll-mt-24"
      data-execution={desk?.execution ?? 'unknown'}
      data-risk={desk?.risk?.new_risk ?? 'unknown'}
    >
      <div className="execution-mode-strip" aria-label="Execution mode">
        <ModeChip label="Execution" value={formatExecution(desk?.execution)} tone={execTone} />
        <ModeChip
          label="Order runway"
          value={formatNewRisk(desk?.risk?.new_risk)}
          tone={
            newRiskTone === 'failed'
              ? 'failed'
              : newRiskTone === 'degraded'
                ? 'degraded'
                : newRiskTone === 'sapphire'
                  ? 'sapphire'
                  : 'neutral'
          }
        />
        <ModeChip label="Posture" value={formatPosture(desk?.posture)} tone="neutral" />
        <ModeChip
          label="Authority"
          value={
            desk?.leader === 'credible'
              ? 'Live'
              : desk?.leader === 'none'
                ? 'Gated'
                : NOT_OBSERVED
          }
          tone={
            desk?.leader === 'credible' ? 'sapphire' : desk?.leader === 'none' ? 'ice' : 'neutral'
          }
        />
      </div>

      <div className="decision-head">
        <div>
          <span className="decision-index">LIVE RAILS</span>
          <h2 id="decision-title">What the plant is doing</h2>
          <p className="decision-sub">
            Designated agentic capital only. Caps, kill switch, and real fills — not backtest
            scoreboards.
          </p>
        </div>
        <div className="decision-next">
          <span>Next useful action</span>
          <p>
            {(desk?.decisions.pending_review ?? 0) > 0
              ? 'Review the decision inbox.'
              : desk?.execution === 'halted' || desk?.execution === 'off'
                ? 'Execution is paused. Nothing fires until a human re-arms.'
                : desk?.risk?.new_risk === 'blocked' || desk?.risk?.new_risk === 'restricted'
                  ? 'Order runway is tight — wait for settlement or free budget.'
                  : 'Plant is accepting gated decisions under caps.'}
          </p>
          <small>{formatPosture(desk?.posture)}</small>
        </div>
      </div>

      {/* Two real rails — RH free-reign + MegaETH MOSS */}
      <div className="rails-grid" aria-label="Designated execution rails">
        <article className="rail-card">
          <header>
            <span className="rail-kicker">Rail 01</span>
            <h3>Robinhood Agentic</h3>
          </header>
          <p>
            Free-reign equity / options / crypto on the designated agentic account. Hard per-order
            and daily caps. Settlement cash gates buys.
          </p>
          <ul>
            <li>
              <span>Mode</span>
              <strong className="tnum">{formatExecution(desk?.execution)}</strong>
            </li>
            <li>
              <span>Risk</span>
              <strong className="tnum">{formatNewRisk(desk?.risk?.new_risk)}</strong>
            </li>
            <li>
              <span>Loss used</span>
              <strong className="tnum">{formatPercent(used)}</strong>
            </li>
          </ul>
        </article>
        <article className="rail-card rail-card--ice">
          <header>
            <span className="rail-kicker">Rail 02</span>
            <h3>MegaETH · MOSS</h3>
          </header>
          <p>
            Session-key USDm transfers under a passkey grant. Transfer-first, 20 USDm/day lab
            ceiling. No private keys on the agent.
          </p>
          <ul>
            <li>
              <span>Grant</span>
              <strong>Passkey · 24h</strong>
            </li>
            <li>
              <span>Scope</span>
              <strong>USDm transfer</strong>
            </li>
            <li>
              <span>Cap</span>
              <strong className="tnum">20 / day</strong>
            </li>
          </ul>
        </article>
      </div>

      <div className="readiness-readouts">
        <div
          className={`capital-runway${runwayCritical ? ' is-critical' : runwayElevated ? ' is-elevated' : ''}`}
        >
          <div className="readout-label">
            <span>Loss allowance</span>
            <strong className="tnum">{formatPercent(used)} used</strong>
          </div>
          <div
            className="runway-track"
            aria-label={`${formatPercent(used)} of ${formatPercent(limit)} loss limit used`}
          >
            <span style={{ width: `${runwayFill}%` }} />
            <i style={{ left: `${runwayFill}%` }} />
          </div>
          <div className="runway-scale">
            <span>0</span>
            <strong className="tnum">
              {formatPercent(desk?.risk?.budget_remaining_pct)} remains
            </strong>
            <span className="tnum">{formatPercent(limit)} stop</span>
          </div>
        </div>
        <div className="trial-clock">
          <span>Research book</span>
          <strong>Single event P</strong>
          <p>
            Binary claims = one probability as-of now. Short / med / long are path targets only.
            <a href="/research/" style={{ marginLeft: 8 }}>
              Open research →
            </a>
          </p>
        </div>
      </div>

      <ol className="readiness-gates" aria-label="Live safety gates">
        {gates.map((gate) => (
          <li key={gate.label} className={`gate-${gate.state}`}>
            <i aria-hidden="true" />
            <span>{gate.label}</span>
            <strong className="tnum">{gate.value}</strong>
          </li>
        ))}
      </ol>

      <div className="decision-tape" aria-label="Decision queue">
        {queue.map((cell, index) => (
          <div
            key={cell.label}
            className={
              cell.blocked
                ? 'is-blocked'
                : cell.gated
                  ? 'is-gated'
                  : cell.protected
                    ? 'is-protected'
                    : undefined
            }
          >
            <span>
              {String(index + 1).padStart(2, '0')} · {cell.label}
            </span>
            <strong className="tnum">{cell.value}</strong>
          </div>
        ))}
      </div>

      <div className="decision-boundary">
        <span>No paper tracks · no fake returns · no backtest theater</span>
        <i aria-hidden="true" />
        <strong>Caps + kill switch always win</strong>
      </div>
    </section>
  )
}

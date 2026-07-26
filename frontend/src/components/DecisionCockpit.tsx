import type { LiveDesk } from '../types'
import { NOT_OBSERVED } from '../desk/format'

const POSTURES: Record<LiveDesk['posture'], string> = {
  capital_preservation: 'Capital preservation',
  selective_risk: 'Selective risk',
  risk_seeking: 'Risk seeking',
  neutral: 'Neutral',
  unknown: NOT_OBSERVED,
}

function ratio(part: number | null, total: number | null, suffix = '') {
  if (part === null || total === null) return NOT_OBSERVED
  return `${part} / ${total}${suffix}`
}

function percent(value: number | null | undefined) {
  if (value === null || value === undefined) return NOT_OBSERVED
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`
}

function signedPercent(value: number) {
  return `${value >= 0 ? '+' : ''}${value.toLocaleString(undefined, {
    maximumFractionDigits: 1,
  })}%`
}

function signedPoints(value: number) {
  return `${value >= 0 ? '+' : ''}${value.toLocaleString(undefined, {
    maximumFractionDigits: 1,
  })}pp`
}

function displayDate(value: string | null | undefined) {
  if (!value) return null
  const date = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

function remainingDays(desk: LiveDesk | null) {
  const qualified = desk?.experiment?.qualified_days
  const required = desk?.experiment?.required_days
  if (qualified === null || qualified === undefined || required === null || required === undefined) {
    return null
  }
  return Math.max(0, required - qualified)
}

function headline(desk: LiveDesk | null) {
  if (!desk || desk.execution === 'unknown') return 'Waiting for desk state.'
  if (desk.execution === 'gated') return 'Trading is gated.'
  return 'Trading stays off.'
}

function nextAction(desk: LiveDesk | null) {
  if (!desk) return 'Waiting for the first complete readiness report.'
  const collector = desk.experiment?.collector
  if (collector === 'stale' || collector === 'missing') {
    return 'Restore evidence collection before another day can qualify.'
  }
  if (desk.risk?.ledger_state === 'unknown') {
    return 'Reconcile the loss ledger before new risk can be assessed.'
  }
  if (releaseBlockers(desk).length > 0) {
    return 'Execution remains withheld until every release condition below clears.'
  }
  if ((desk.decisions.pending_review ?? 0) > 0) return 'Review the decision inbox.'
  return 'All observed gates are aligned.'
}

function releaseBlockers(desk: LiveDesk | null) {
  if (!desk) return []
  const blockers: string[] = []
  const missingFeeds = Math.max(0, (desk.feeds.total ?? 0) - (desk.feeds.fresh ?? 0))
  if (missingFeeds > 0) blockers.push(`${missingFeeds} stale ${missingFeeds === 1 ? 'feed' : 'feeds'}`)
  if (desk.risk?.ledger_state !== 'reconciled') blockers.push('Loss ledger')
  if (desk.experiment?.collector === 'stale' || desk.experiment?.collector === 'missing') {
    blockers.push('Evidence collector')
  }
  const remaining = remainingDays(desk)
  if (remaining && remaining > 0) blockers.push(`${remaining} evidence ${remaining === 1 ? 'day' : 'days'}`)
  if (
    desk.validation.oos_pass !== null
    && desk.validation.oos_pass !== undefined
    && desk.validation.oos_pass <= 0
  ) {
    blockers.push('Positive OOS')
  }
  const conflicts = desk.validation.conflicts ?? 0
  if (conflicts > 0) blockers.push(`${conflicts} ${conflicts === 1 ? 'conflict' : 'conflicts'}`)
  if (desk.risk?.new_risk === 'restricted' || desk.risk?.new_risk === 'blocked') {
    blockers.push('Order runway')
  }
  if (
    desk.leader !== 'credible'
    && !remaining
    && (desk.validation.oos_pass ?? 0) > 0
    && conflicts === 0
  ) {
    blockers.push('Execution authority')
  }
  return blockers
}

export function DecisionCockpit({ desk }: { desk: LiveDesk | null }) {
  const used = desk?.risk?.realized_drawdown_pct
  const limit = desk?.risk?.drawdown_limit_pct
  const runwayFill = used !== null && used !== undefined && limit
    ? Math.min(100, Math.max(0, used * 100 / limit))
    : 0
  const gates = [
    {
      label: 'Data',
      value: desk ? ratio(desk.feeds.fresh, desk.feeds.total, ' current') : NOT_OBSERVED,
      state: desk && desk.feeds.fresh === desk.feeds.total ? 'pass' : 'hold',
    },
    {
      label: 'Loss ledger',
      value: desk?.risk?.ledger_state === 'reconciled' ? 'Reconciled' : NOT_OBSERVED,
      state: desk?.risk?.ledger_state === 'reconciled' ? 'pass' : 'hold',
    },
    {
      label: 'OOS',
      value: desk ? ratio(desk.validation.oos_pass, desk.validation.oos_total, ' pass') : NOT_OBSERVED,
      state: (desk?.validation.oos_pass ?? 0) > 0 ? 'pass' : 'hold',
    },
    {
      label: 'Sealed trial',
      value: desk?.experiment
        ? ratio(desk.experiment.qualified_days, desk.experiment.required_days)
        : NOT_OBSERVED,
      state:
        desk?.experiment?.qualified_days === desk?.experiment?.required_days
          ? 'pass'
          : 'hold',
    },
    {
      label: 'Order runway',
      value:
        desk?.risk?.new_risk === 'available'
          ? 'Available'
          : desk?.risk?.new_risk === 'unknown' || !desk?.risk
            ? NOT_OBSERVED
            : 'Restricted',
      state: desk?.risk?.new_risk === 'available' ? 'pass' : 'hold',
    },
    {
      label: 'Authority',
      value: desk?.leader === 'credible' ? 'Earned' : desk?.leader === 'none' ? 'Withheld' : NOT_OBSERVED,
      state: desk?.leader === 'credible' ? 'pass' : 'hold',
    },
  ] as const
  const blockers = releaseBlockers(desk)
  const conflictDetails = desk?.validation.conflict_details ?? []
  const maxConflictGap = Math.max(1, ...conflictDetails.map((item) => item.gap_pp))
  const queue = [
    { label: 'Awaiting review', value: desk?.decisions.pending_review ?? NOT_OBSERVED },
    { label: 'Blocked before review', value: desk?.decisions.pending_policy_blocked ?? NOT_OBSERVED },
    { label: 'Approved unresolved', value: desk?.decisions.approved_awaiting_execution ?? NOT_OBSERVED },
    { label: 'Execution eligible', value: desk?.decisions.eligible_execution ?? NOT_OBSERVED },
    {
      label: 'Blocked by policy',
      value: desk?.decisions.blocked ?? NOT_OBSERVED,
      blocked: (desk?.decisions.blocked ?? 0) > 0,
    },
    {
      label: 'Execution',
      value: desk?.execution === 'unknown' || !desk
        ? NOT_OBSERVED
        : desk.execution[0].toUpperCase() + desk.execution.slice(1),
      protected: desk?.execution === 'halted' || desk?.execution === 'off',
    },
  ]

  return (
    <section
      id="decisions"
      aria-labelledby="decision-title"
      className="decision-cockpit scroll-mt-24"
    >
      <div className="decision-head">
        <div>
          <span className="decision-index">READINESS / CAPITAL RUNWAY</span>
          <h2 id="decision-title">{headline(desk)}</h2>
        </div>
        <div className="decision-next">
          <span>Release conditions</span>
          <p>{nextAction(desk)}</p>
          {blockers.length > 0 ? (
            <ul className="decision-blockers" aria-label="Current release blockers">
              {blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
            </ul>
          ) : null}
          <small>{desk ? POSTURES[desk.posture] : NOT_OBSERVED}</small>
        </div>
      </div>
      <div className="readiness-readouts">
        <div className="capital-runway">
          <div className="readout-label">
            <span>Loss allowance</span>
            <strong>{percent(used)} used</strong>
          </div>
          <div className="runway-track" aria-label={`${percent(used)} of ${percent(limit)} loss limit used`}>
            <span style={{ width: `${runwayFill}%` }} />
            <i style={{ left: `${runwayFill}%` }} />
          </div>
          <div className="runway-scale">
            <span>0</span>
            <strong>{percent(desk?.risk?.budget_remaining_pct)} remains</strong>
            <span>{percent(limit)} stop</span>
          </div>
        </div>
        <div className="trial-clock">
          <span>Sealed trial</span>
          <strong>
            {desk?.experiment
              ? ratio(desk.experiment.qualified_days, desk.experiment.required_days)
              : NOT_OBSERVED}
          </strong>
          <p>
            Collector {desk?.experiment?.collector ?? 'not observed'}
            {desk?.experiment?.last_committed_date
              ? ` · through ${desk.experiment.last_committed_date}`
              : ''}
          </p>
        </div>
      </div>
      {conflictDetails.length > 0 ? (
        <div className="validation-ledger" aria-label="Live and replay validation conflicts">
          <div className="validation-ledger-head">
            <div>
              <span>Live / replay audit</span>
              <strong>
                {conflictDetails.length} material
                {' '}
                {conflictDetails.length === 1 ? 'contradiction' : 'contradictions'}
              </strong>
            </div>
            <p>
              Live paper is materially hotter than replay. These results remain untrusted.
              {desk?.validation.replay_span_hours !== null
                && desk?.validation.replay_span_hours !== undefined
                ? ` Replay: ${desk.validation.replay_span_hours.toLocaleString(undefined, {
                    maximumFractionDigits: 1,
                  })} hours`
                : ''}
              {displayDate(desk?.validation.replay_data_through)
                ? ` · through ${displayDate(desk?.validation.replay_data_through)}`
                : ''}
            </p>
          </div>
          <ol>
            {conflictDetails.map((item, index) => (
              <li key={item.strategy}>
                <span className="validation-rank">{String(index + 1).padStart(2, '0')}</span>
                <strong>{item.strategy}</strong>
                <div className="validation-gap" aria-hidden="true">
                  <i style={{ width: `${Math.max(4, item.gap_pp * 100 / maxConflictGap)}%` }} />
                </div>
                <span>{signedPercent(item.live_return_pct)} live</span>
                <span>{signedPercent(item.replay_return_pct)} replay</span>
                <b>{signedPoints(item.gap_pp)}</b>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      <ol className="readiness-gates" aria-label="Promotion gates">
        {gates.map((gate) => (
          <li key={gate.label} className={`gate-${gate.state}`}>
            <i aria-hidden="true" />
            <span>{gate.label}</span>
            <strong>{gate.value}</strong>
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
                : cell.protected
                  ? 'is-protected'
                  : undefined
            }
          >
            <span>{String(index + 1).padStart(2, '0')} · {cell.label}</span>
            <strong>{cell.value}</strong>
          </div>
        ))}
      </div>
      <div className="decision-boundary">
        <span>Evidence can challenge the mandate; it cannot silently replace it</span>
        <i aria-hidden="true" />
        <strong>Only completed gates release execution</strong>
      </div>
    </section>
  )
}

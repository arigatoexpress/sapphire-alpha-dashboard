import type { LiveDesk, PublicTrack } from '../types'
import {
  executionTone,
  formatAge,
  formatExecution,
  formatExecutionHeadline,
  formatNewRisk,
  formatPercent,
  formatPosture,
  formatRatio,
  formatSignedPercent,
  formatSignedPoints,
  NOT_OBSERVED,
  riskTone,
} from '../desk/format'

type ValidationConflict = NonNullable<LiveDesk['validation']['conflict_details']>[number]

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
    return 'Execution remains withheld until every release condition below clears. Untrusted paper marks never unlock the start button.'
  }
  if ((desk.decisions.pending_review ?? 0) > 0) return 'Review the decision inbox.'
  return 'All observed gates are aligned.'
}

/** Live/replay conflict or data-quality flag → paper mark is not leadership-eligible. */
function trackIsUntrusted(
  track: PublicTrack,
  conflict: ValidationConflict | undefined,
) {
  return Boolean(conflict) || (track.data_flags ?? 0) > 0
}

function trackTrustLabel(
  track: PublicTrack,
  conflict: ValidationConflict | undefined,
) {
  if (conflict) {
    return conflict.gap_pp >= 20
      ? 'Untrusted · disqualified'
      : 'Replay conflict'
  }
  if ((track.data_flags ?? 0) > 0) {
    return `${track.data_flags} data ${track.data_flags === 1 ? 'flag' : 'flags'} · untrusted`
  }
  if (track.status === 'inactive') return 'Flat / inactive'
  if (track.status === 'stale') return 'Stale'
  return 'Paper only'
}

function sortTracksForDisplay(
  tracks: PublicTrack[],
  conflictByStrategy: Map<string, ValidationConflict>,
) {
  return [...tracks].sort((a, b) => {
    const aUntrusted = trackIsUntrusted(a, conflictByStrategy.get(a.strategy)) ? 1 : 0
    const bUntrusted = trackIsUntrusted(b, conflictByStrategy.get(b.strategy)) ? 1 : 0
    if (aUntrusted !== bUntrusted) return aUntrusted - bUntrusted
    if (a.status === 'inactive' && b.status !== 'inactive') return 1
    if (b.status === 'inactive' && a.status !== 'inactive') return -1
    return a.strategy.localeCompare(b.strategy)
  })
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

export function DecisionCockpit({ desk }: { desk: LiveDesk | null }) {
  const used = desk?.risk?.realized_drawdown_pct
  const limit = desk?.risk?.drawdown_limit_pct
  const runwayFill = used !== null && used !== undefined && limit
    ? Math.min(100, Math.max(0, used * 100 / limit))
    : 0
  const runwayCritical = runwayFill >= 90
  const runwayElevated = runwayFill >= 70
  const execTone = executionTone(desk?.execution)
  const newRiskTone = riskTone(desk?.risk?.new_risk)
  const gates = [
    {
      label: 'Data',
      value: desk ? formatRatio(desk.feeds.fresh, desk.feeds.total, ' current') : NOT_OBSERVED,
      state: desk && desk.feeds.fresh === desk.feeds.total ? 'pass' : 'hold',
    },
    {
      label: 'Loss ledger',
      value: desk?.risk?.ledger_state === 'reconciled' ? 'Reconciled' : NOT_OBSERVED,
      state: desk?.risk?.ledger_state === 'reconciled' ? 'pass' : 'hold',
    },
    {
      label: 'OOS',
      value: desk ? formatRatio(desk.validation.oos_pass, desk.validation.oos_total, ' pass') : NOT_OBSERVED,
      state: (desk?.validation.oos_pass ?? 0) > 0 ? 'pass' : 'hold',
    },
    {
      label: 'Sealed trial',
      value: desk?.experiment
        ? formatRatio(desk.experiment.qualified_days, desk.experiment.required_days)
        : NOT_OBSERVED,
      state:
        desk?.experiment?.qualified_days === desk?.experiment?.required_days
          ? 'pass'
          : 'hold',
    },
    {
      label: 'Order runway',
      value: formatNewRisk(desk?.risk?.new_risk),
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
  const conflictByStrategy = new Map(
    conflictDetails.map((conflict) => [conflict.strategy, conflict]),
  )
  const paperTracks = sortTracksForDisplay(desk?.tracks ?? [], conflictByStrategy)
  const untrustedTrackCount = paperTracks.filter((track) =>
    trackIsUntrusted(track, conflictByStrategy.get(track.strategy)),
  ).length
  const maxConflictGap = Math.max(1, ...conflictDetails.map((item) => item.gap_pp))
  const queue = [
    { label: 'Awaiting review', value: desk?.decisions.pending_review ?? NOT_OBSERVED },
    { label: 'Blocked before review', value: desk?.decisions.pending_policy_blocked ?? NOT_OBSERVED },
    { label: 'Approved, active', value: desk?.decisions.approved_awaiting_execution ?? NOT_OBSERVED },
    { label: 'Execution eligible', value: desk?.decisions.eligible_execution ?? NOT_OBSERVED },
    {
      label: 'Approved but blocked',
      value: desk?.decisions.blocked ?? NOT_OBSERVED,
      blocked: (desk?.decisions.blocked ?? 0) > 0,
    },
    {
      label: 'Execution',
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
      {/* Mode strip: execution · risk · posture at a glance */}
      <div className="execution-mode-strip" aria-label="Execution mode">
        <ModeChip
          label="Execution"
          value={formatExecution(desk?.execution)}
          tone={execTone}
        />
        <ModeChip
          label="Order runway"
          value={formatNewRisk(desk?.risk?.new_risk)}
          tone={newRiskTone === 'failed' ? 'failed' : newRiskTone === 'degraded' ? 'degraded' : newRiskTone === 'sapphire' ? 'sapphire' : 'neutral'}
        />
        <ModeChip
          label="Posture"
          value={formatPosture(desk?.posture)}
          tone="neutral"
        />
        <ModeChip
          label="Authority"
          value={
            desk?.leader === 'credible'
              ? 'Earned'
              : desk?.leader === 'none'
                ? 'Withheld'
                : NOT_OBSERVED
          }
          tone={desk?.leader === 'credible' ? 'sapphire' : desk?.leader === 'none' ? 'ice' : 'neutral'}
        />
      </div>

      <div className="decision-head">
        <div>
          <span className="decision-index">READINESS / CAPITAL RUNWAY</span>
          <h2 id="decision-title">{formatExecutionHeadline(desk?.execution)}</h2>
        </div>
        <div className="decision-next">
          <span>Release conditions</span>
          <p>{nextAction(desk)}</p>
          {blockers.length > 0 ? (
            <ul className="decision-blockers" aria-label="Current release blockers">
              {blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
            </ul>
          ) : null}
          <small>{formatPosture(desk?.posture)}</small>
        </div>
      </div>
      <div className="readiness-readouts">
        <div className={`capital-runway${runwayCritical ? ' is-critical' : runwayElevated ? ' is-elevated' : ''}`}>
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
            <strong className="tnum">{formatPercent(desk?.risk?.budget_remaining_pct)} remains</strong>
            <span className="tnum">{formatPercent(limit)} stop</span>
          </div>
        </div>
        <div className="trial-clock">
          <span>Sealed trial</span>
          <strong className="tnum">
            {desk?.experiment
              ? formatRatio(desk.experiment.qualified_days, desk.experiment.required_days)
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
      {paperTracks.length > 0 ? (
        <div className="strategy-ledger" aria-label="Paper strategy evidence">
          <div className="strategy-ledger-head">
            <div>
              <span>Paper strategy evidence</span>
              <strong>
                {paperTracks.length} reporting tracks
                {untrustedTrackCount > 0
                  ? ` · ${untrustedTrackCount} untrusted`
                  : ''}
              </strong>
            </div>
            <p>
              Live return, evidence clock, open simulations, and data quality.
              Paper performance never grants execution authority. Contaminated
              or conflicted marks stay untrusted and cannot lead.
            </p>
          </div>
          <ol>
            {paperTracks.map((track) => {
              const conflict = conflictByStrategy.get(track.strategy)
              const untrusted = trackIsUntrusted(track, conflict)
              const progress = Math.min(
                100,
                Math.max(0, track.green_days * 100 / track.target_days),
              )
              const quality = trackTrustLabel(track, conflict)
              const returnClass = untrusted
                ? 'is-untrusted'
                : track.live_return_pct > 0
                  ? 'is-positive'
                  : track.live_return_pct < 0
                    ? 'is-negative'
                    : undefined
              return (
                <li
                  key={track.strategy}
                  className={untrusted ? 'is-untrusted-track' : undefined}
                >
                  <span
                    className={`strategy-status strategy-status-${track.status}${untrusted ? ' strategy-status-untrusted' : ''}`}
                    aria-label={`${track.status}${untrusted ? ', untrusted' : ''}, observed ${formatAge(track.freshness_s)}`}
                  />
                  <strong>{track.strategy}</strong>
                  <span className={`tnum ${returnClass ?? ''}`}>
                    {formatSignedPercent(track.live_return_pct)} live
                    {untrusted ? ' · untrusted' : ''}
                  </span>
                  <span className="tnum">
                    {conflict
                      ? `${formatSignedPercent(conflict.replay_return_pct)} replay`
                      : 'Replay not matched'}
                  </span>
                  <div>
                    <span className="tnum">{track.green_days} / {track.target_days}</span>
                    <i aria-hidden="true"><b style={{ width: `${progress}%` }} /></i>
                  </div>
                  <span className="tnum">{track.open_count} open</span>
                  <b className={untrusted || track.status === 'stale' ? 'is-warning' : ''}>
                    <span>{quality}</span>
                    <small>{formatAge(track.freshness_s)}</small>
                  </b>
                </li>
              )
            })}
          </ol>
        </div>
      ) : null}
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
                <span className="tnum">{formatSignedPercent(item.live_return_pct)} live</span>
                <span className="tnum">{formatSignedPercent(item.replay_return_pct)} replay</span>
                <b className="tnum">{formatSignedPoints(item.gap_pp)}</b>
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
            <span>{String(index + 1).padStart(2, '0')} · {cell.label}</span>
            <strong className="tnum">{cell.value}</strong>
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

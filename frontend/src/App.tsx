import { useMemo, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { narrate } from '@shared/narrate'
import { describeAgent, describeNode } from '@shared/vocabulary'
import { shortBuildValue } from '@shared/build'
import { useFleet } from './hooks/useFleet'
import { useBuildIdentity } from './hooks/useBuildIdentity'
import { useLiveTelemetry } from './hooks/useLiveTelemetry'
import { useMossSnapshot } from './hooks/useMossSnapshot'
import { usePublicWidgets } from './hooks/usePublicWidgets'
import {
  formatAge,
  formatClockTime,
  formatCount,
  formatObservedAt,
  NOT_OBSERVED,
} from './desk/format'
import type {
  FleetCounts,
  FleetData,
  LiveEvent,
  LiveSnapshot,
  MossSnapshot,
  PublicWidgets,
} from './types'

type EvidenceTone = 'current' | 'held' | 'degraded' | 'unknown'

interface EvidenceSegment {
  id: string
  label: string
  value: string
  source: string
  observedAt: string
  freshness: string
  authority: string
  uncertainty: string
  tone: EvidenceTone
}

interface AttentionItem {
  label: string
  detail: string
  tone: EvidenceTone
}

const SECTIONS = [
  { href: '#thesis', label: 'Thesis' },
  { href: '#attention', label: 'Attention' },
  { href: '#timeline', label: 'Changed' },
  { href: '#evidence', label: 'Evidence' },
]
const RUNTIME_TTL_SECONDS = 180

function words(value: string | null | undefined) {
  return value ? value.replace(/_/g, ' ') : NOT_OBSERVED
}

function observedTime(value: string | null | undefined) {
  return formatObservedAt(value)
}

function isFleetCounts(fleet: FleetData | FleetCounts): fleet is FleetCounts {
  return !('counts' in fleet)
}

function fleetCount(fleet: FleetData | FleetCounts | null, key: 'leases' | 'gates') {
  if (
    !fleet ||
    fleet.snapshot_age_s == null ||
    fleet.snapshot_age_s > RUNTIME_TTL_SECONDS
  ) return null
  if (isFleetCounts(fleet)) return key === 'leases' ? fleet.leases : fleet.gates_open
  return key === 'leases' ? fleet.counts.leases : fleet.counts.gates_open
}

function toneForValue(value: string | null | undefined): EvidenceTone {
  const normalized = String(value ?? '').toLowerCase()
  if (!normalized || normalized === NOT_OBSERVED || normalized === 'unknown') return 'unknown'
  if (['halted', 'off', 'gated', 'disarmed', 'read-only'].includes(normalized)) return 'held'
  if (['stale', 'delayed', 'degraded', 'down', 'offline', 'failed'].includes(normalized)) {
    return 'degraded'
  }
  if (['live', 'current', 'healthy', 'verified', 'working', 'recovered', 'observed'].includes(normalized)) {
    return 'current'
  }
  return 'unknown'
}

function percent(value: number | null | undefined, digits = 0) {
  return value == null ? NOT_OBSERVED : `${(value * 100).toFixed(digits)}%`
}

export default function App(
  {
    initialWidgets,
    initialSnapshot,
  }: {
    initialWidgets?: PublicWidgets
    initialSnapshot?: LiveSnapshot
  } = {},
) {
  const build = useBuildIdentity()
  const { snapshot: polledSnapshot, error, loading } = useLiveTelemetry()
  const snapshot = initialSnapshot ?? polledSnapshot
  const { snapshot: moss, error: mossError } = useMossSnapshot()
  const { fleet, error: fleetError } = useFleet()
  const { widgets: polledWidgets, error: widgetsError } = usePublicWidgets()
  const widgets = initialWidgets ?? polledWidgets

  const execution =
    snapshot?.status === 'live'
      ? snapshot?.desk?.execution ?? snapshot?.markets.execution ?? null
      : null
  const status = error ? 'unavailable' : (snapshot?.status ?? (loading ? 'warming' : 'not observed'))
  const narration = useMemo(() => (snapshot ? narrate(snapshot) : null), [snapshot])
  const gateCount = fleetCount(fleet, 'gates')
  const leaseCount = fleetCount(fleet, 'leases')
  const epistemics =
    snapshot?.status === 'live' && snapshot.desk?.epistemics?.fresh
      ? snapshot.desk.epistemics
      : null
  const thesis = epistemics?.thesis

  const segments = useMemo(
    () =>
      buildEvidenceSegments({
        snapshot,
        widgets,
        moss,
        fleet,
        execution,
        errors: { live: error, widgets: widgetsError, fleet: fleetError, moss: mossError },
      }),
    [snapshot, widgets, moss, fleet, execution, error, widgetsError, fleetError, mossError],
  )
  const [activeId, setActiveId] = useState('snapshot')
  const activeEvidence = segments.find((segment) => segment.id === activeId) ?? segments[0]

  const attention = useMemo(
    () =>
      buildAttention({
        snapshot,
        widgets,
        execution,
        error,
        widgetsError,
        fleetError,
        mossError,
        gateCount,
      }),
    [
      snapshot,
      widgets,
      execution,
      error,
      widgetsError,
      fleetError,
      mossError,
      gateCount,
    ],
  )

  const attentionCount = attention.length
    ? formatCount(attention.length)
    : snapshot?.observed_at
      ? '0'
      : NOT_OBSERVED

  const decision = deriveCurrentDecision({
    snapshot,
    widgets,
    execution,
    error,
    attention,
  })

  return (
    <div className="observatory-shell" data-execution={execution ?? 'unknown'}>
      <div className="observatory-glow" aria-hidden="true" />

      <header className="observatory-header">
        <a className="observatory-brand" href="/">
          <span aria-hidden="true">◇</span>
          Sapphire <b>Mission Control</b>
        </a>
        <nav aria-label="Observatory sections">
          {SECTIONS.map((section) => (
            <a href={section.href} key={section.href}>
              {section.label}
            </a>
          ))}
        </nav>
        <div className="observatory-header-state">
          <span className={`state-dot state-dot--${toneForValue(status)}`} aria-hidden="true" />
          <span>{status}</span>
          <time>{error && snapshot ? `last report ${formatAge(snapshot.freshness_s)}` : formatAge(snapshot?.freshness_s)}</time>
        </div>
      </header>

      <main className="observatory-main">
        <RuntimeStrip snapshot={snapshot} error={error} />

        <section
          className="current-decision-band"
          aria-labelledby="current-decision-title"
          data-decision={decision.verb}
        >
          <p className="observatory-kicker">CURRENT DECISION</p>
          <h1 id="current-decision-title">
            <span className="current-decision-verb">{decision.verb}</span>
            <span className="current-decision-detail">{decision.summary}</span>
          </h1>
          <div className="current-decision-grid" role="group" aria-label="Decision factors">
            <div>
              <span>Pause + authority</span>
              <strong data-tone={decision.pauseTone}>{decision.pause}</strong>
            </div>
            <div>
              <span>Evidence freshness</span>
              <strong data-tone={decision.freshnessTone}>{decision.freshness}</strong>
            </div>
            <div>
              <span>Exact next gate</span>
              <strong data-tone={decision.nextTone}>{decision.nextGate}</strong>
            </div>
          </div>
          <p className="current-decision-thesis">
            Thesis: {thesis?.claim ?? 'No thesis observed.'}
            {' · '}
            Attention items: {attentionCount}
          </p>
        </section>

        <section className="observatory-opening" aria-labelledby="observatory-title">
          <div>
            <p className="observatory-kicker">Operator desk · read-only view</p>
            <h2 id="observatory-title">{thesis?.claim ?? 'No thesis observed.'}</h2>
            <p className="observatory-lede">
              What is true, what is stale, what is blocked, and what exact attended action
              is next — without presenting absence as health.
            </p>
          </div>

          <div className="observatory-opening-facts" aria-label="Current thesis summary">
            <div>
              <span>Probability</span>
              <strong>{percent(thesis?.probability)}</strong>
            </div>
            <div>
              <span>Stance</span>
              <strong>{words(thesis?.stance)}</strong>
            </div>
            <div>
              <span>Horizon</span>
              <strong>{thesis ? `${thesis.horizon_days} days` : NOT_OBSERVED}</strong>
            </div>
            <div>
              <span>Needs attention</span>
              <strong>{attentionCount}</strong>
            </div>
          </div>
        </section>

        <ThesisPulse
          snapshot={snapshot}
          execution={execution}
        />

        <EvidenceHorizon
          segments={segments}
          active={activeEvidence}
          onSelect={setActiveId}
        />

        <div className="observatory-decision-grid">
          <section id="attention" className="attention-panel" aria-labelledby="attention-title">
            <div className="section-heading">
              <p>02 · Needs attention</p>
              <h2 id="attention-title">The shortest path to a truthful state.</h2>
            </div>
            {attention.length ? (
              <ol className="attention-list">
                {attention.map((item, index) => (
                  <li key={`${item.label}-${index}`} data-tone={item.tone}>
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <div>
                      <strong>{item.label}</strong>
                      <p>{item.detail}</p>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <div className="timeline-empty">
                <span>{snapshot?.observed_at ? 'No urgent exception observed' : 'No report yet'}</span>
                <p>
                  {snapshot?.observed_at
                    ? 'This is bounded to the current snapshot; it is not a claim that every subsystem is healthy.'
                    : 'Waiting for the first report before counting exceptions.'}
                </p>
              </div>
            )}
            <p className="attention-boundary">
              This page observes the desk. Start/stop, policy changes, custody, and orders
              remain isolated control surfaces.
            </p>
          </section>

          <section id="timeline" className="timeline-panel" aria-labelledby="timeline-title">
            <div className="section-heading">
              <p>03 · What changed</p>
              <h2 id="timeline-title">Observed events, newest first.</h2>
            </div>
            <EventTimeline snapshot={snapshot} fallback={narration?.text} />
          </section>
        </div>

        <section id="evidence" className="evidence-ledger" aria-labelledby="evidence-title">
          <div className="section-heading section-heading--wide">
            <div>
              <p>04 · Evidence</p>
              <h2 id="evidence-title">The details stay available, not dominant.</h2>
            </div>
            <p>
              Open a ledger only when the decision needs it. The top of the page stays
              reserved for thesis, revision triggers, and execution availability.
            </p>
          </div>

          <div className="evidence-disclosures">
            <ResearchDisclosure widgets={widgets} />
            <SystemDisclosure snapshot={snapshot} leaseCount={leaseCount} />
            <AssetDisclosure
              status={moss?.status}
              funding={moss?.usdm_band}
              authority={moss?.authority}
            />
          </div>
        </section>

        <section className="measurement-contract" aria-label="Measurement contract">
          <p>Measurement contract</p>
          <h2>A number is observed, or it is absent.</h2>
          <div>
            <p>
              Every figure is tied to the report that supplied it. Missing source,
              freshness, or authority makes the value unknown—not zero, safe, or live.
            </p>
            <p>
              Capital remains banded. Identities, addresses, holdings, orders, and machine
              names never enter this anonymous surface.
            </p>
          </div>
        </section>
      </main>

      <footer className="observatory-footer">
        <span>Sapphire Alpha · conviction under revision</span>
        {build ? (
          <span>
            Build {shortBuildValue(build.source_sha)} ·{' '}
            {shortBuildValue(build.build_id, 16)} · {build.runtime_revision} ·{' '}
            {build.surfaces.operator.asset_count + build.surfaces.public.asset_count} files ·{' '}
            {shortBuildValue(build.surfaces.operator.manifest_sha256, 8)}/
            {shortBuildValue(build.surfaces.public.manifest_sha256, 8)} ·{' '}
            {build.complete ? 'attributed' : 'incomplete'} ·{' '}
            <a href="/api/build">manifest</a>
          </span>
        ) : (
          <span>
            Build not verified · <a href="/api/build">inspect manifest</a>
          </span>
        )}
        <span>Anonymous · read-only view · controls isolated</span>
      </footer>
    </div>
  )
}

function RuntimeStrip({
  snapshot,
  error,
}: {
  snapshot: LiveSnapshot | null
  error: string
}) {
  const reportCurrent = snapshot?.status === 'live' && !error
  const currentComponents = reportCurrent
    ? snapshot.nodes.filter(
        (node) => node.status === 'healthy' && node.freshness_s <= RUNTIME_TTL_SECONDS,
      ).length
    : null
  const homeCompute = reportCurrent
    ? snapshot.nodes.find((node) => node.id === 'win-workhorse')
    : null

  return (
    <section className="runtime-strip" aria-labelledby="runtime-strip-title">
      <p id="runtime-strip-title">SYSTEM NOW</p>
      <div className="runtime-strip-grid">
        <div>
          <span>Snapshot</span>
          <strong>
            {snapshot
              ? error
                ? `poll failed · last report ${formatAge(snapshot.freshness_s)}`
                : `${snapshot.status} · ${formatAge(snapshot.freshness_s)}`
              : NOT_OBSERVED}
          </strong>
        </div>
        <div>
          <span>Market activity</span>
          <strong>
            {reportCurrent && snapshot.markets.events_per_min != null
              ? `${formatCount(snapshot.markets.events_per_min)} / min`
              : NOT_OBSERVED}
          </strong>
        </div>
        <div>
          <span>Current components</span>
          <strong>
            {currentComponents != null
              ? `${formatCount(currentComponents)} / ${formatCount(snapshot?.nodes.length)}`
              : NOT_OBSERVED}
          </strong>
        </div>
        <div>
          <span>Home compute</span>
          <strong>
            {homeCompute
              ? `${homeCompute.status} · ${formatAge(homeCompute.freshness_s)}`
              : NOT_OBSERVED}
          </strong>
        </div>
      </div>
    </section>
  )
}

function ThesisPulse({
  snapshot,
  execution,
}: {
  snapshot: LiveSnapshot | null
  execution: string | null
}) {
  const runtimeCurrent = snapshot?.status === 'live'
  const epistemics =
    runtimeCurrent && snapshot.desk?.epistemics?.fresh
      ? snapshot.desk.epistemics
      : null
  const thesis = epistemics?.thesis
  const regime = epistemics?.regime
  const learning = epistemics?.learning
  const falsifier = epistemics?.falsifiers?.[0]
  const autonomy = runtimeCurrent ? snapshot.desk?.autonomy : null
  const floor = runtimeCurrent ? snapshot.desk?.safety_floor : null
  const floorChecks = floor
    ? [floor.gate_valid, floor.pause_clear, floor.ledger === 'reconciled', floor.bounded_policy]
    : []
  const floorReady = floorChecks.length === 4 && floorChecks.every(Boolean)

  const stages = [
    {
      id: 'claim',
      eyebrow: 'Claim',
      title: 'Thesis now',
      value: thesis?.claim ?? 'No thesis observed.',
      meta: thesis
        ? `${percent(thesis.probability)} probability · ${words(thesis.confidence)} confidence`
        : 'Waiting for a versioned claim.',
      tone: thesis ? (epistemics?.fresh ? 'current' : 'degraded') : 'unknown',
    },
    {
      id: 'regime',
      eyebrow: 'Context',
      title: 'Narrative & regime',
      value: regime?.label ? words(regime.label) : NOT_OBSERVED,
      meta: regime?.drivers?.length
        ? regime.drivers.slice(0, 2).join(' · ')
        : `Fit ${percent(regime?.fit)} · quality ${percent(regime?.data_quality)}`,
      tone: regime?.label && regime.label !== 'unknown' ? 'current' : 'unknown',
    },
    {
      id: 'falsifier',
      eyebrow: 'Revision trigger',
      title: 'What would change the view',
      value: falsifier?.condition ?? thesis?.falsifier ?? NOT_OBSERVED,
      meta: falsifier ? `Status: ${words(falsifier.status)}` : 'No falsifier observed.',
      tone: falsifier?.status === 'triggered'
        ? 'degraded'
        : falsifier?.status === 'watch'
          ? 'held'
          : falsifier
            ? 'current'
            : 'unknown',
    },
    {
      id: 'learning',
      eyebrow: 'Outcomes',
      title: 'Learning loop',
      value: learning
        ? `${formatCount(learning.open)} open · ${formatCount(learning.resolved)} resolved`
        : NOT_OBSERVED,
      meta: learning
        ? `Brier ${learning.mean_brier == null ? NOT_OBSERVED : learning.mean_brier.toFixed(3)} · ${formatCount(learning.lessons)} lessons`
        : 'No outcome calibration observed.',
      tone: learning?.status === 'learning'
        ? 'current'
        : learning?.status === 'bootstrapping'
          ? 'held'
          : 'unknown',
    },
    {
      id: 'execution',
      eyebrow: 'Availability',
      title: 'Execution floor',
      value: floor ? (floorReady ? 'Ready' : 'Waiting') : NOT_OBSERVED,
      meta: floor
        ? `${floor.ledger} ledger · ${autonomy?.new_entries ?? 'waiting'} entries · execution ${words(execution)}`
        : 'Gate, pause, ledger, and bounded policy are not observed.',
      tone: floorReady && autonomy?.active ? 'current' : floor ? 'held' : 'unknown',
    },
  ] as const

  return (
    <section id="thesis" className="thesis-pulse" aria-labelledby="thesis-pulse-title">
      <div className="thesis-pulse-heading">
        <div>
          <p>01 · Thesis pulse</p>
          <h2 id="thesis-pulse-title">One view. Five revision points.</h2>
        </div>
        <p>
          {autonomy
            ? `Autonomy desired ${autonomy.desired}; effective ${autonomy.active ? 'on' : 'off'} — ${autonomy.reason}.`
            : 'Autonomy state has not been observed.'}
        </p>
      </div>
      <ol className="thesis-pulse-track">
        {stages.map((stage, index) => (
          <li key={stage.id} data-tone={stage.tone}>
            <span className="thesis-pulse-index">{String(index + 1).padStart(2, '0')}</span>
            <div>
              <p>{stage.eyebrow}</p>
              <h3>{stage.title}</h3>
              <strong>{stage.value}</strong>
              <small>{stage.meta}</small>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function EvidenceHorizon({
  segments,
  active,
  onSelect,
}: {
  segments: EvidenceSegment[]
  active: EvidenceSegment
  onSelect: (id: string) => void
}) {
  function moveFocus(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const keyOffsets: Record<string, number> = {
      ArrowRight: 1,
      ArrowDown: 1,
      ArrowLeft: -1,
      ArrowUp: -1,
    }
    let nextIndex = index
    if (event.key === 'Home') nextIndex = 0
    else if (event.key === 'End') nextIndex = segments.length - 1
    else if (event.key in keyOffsets) {
      nextIndex = (index + keyOffsets[event.key] + segments.length) % segments.length
    } else {
      return
    }
    event.preventDefault()
    onSelect(segments[nextIndex].id)
    document.getElementById(`evidence-tab-${segments[nextIndex].id}`)?.focus()
  }

  return (
    <section className="evidence-horizon horizon-enter" aria-labelledby="horizon-title">
      <div className="evidence-horizon-heading">
        <div>
          <p>Evidence horizon</p>
          <h2 id="horizon-title">Freshness and authority share one line.</h2>
        </div>
        <span>Focus a segment for provenance</span>
      </div>

      <div className="evidence-horizon-track" role="tablist" aria-label="Evidence sources">
        {segments.map((segment, index) => (
          <button
            key={segment.id}
            id={`evidence-tab-${segment.id}`}
            type="button"
            role="tab"
            aria-selected={segment.id === active.id}
            aria-controls="evidence-horizon-detail"
            tabIndex={segment.id === active.id ? 0 : -1}
            data-tone={segment.tone}
            data-evidence-state={
              segment.tone === 'current'
                ? 'observed'
                : segment.tone === 'degraded'
                  ? 'stale'
                  : segment.tone === 'held'
                    ? 'paused'
                    : segment.value === NOT_OBSERVED
                      ? 'unavailable'
                      : 'source-only'
            }
            onClick={() => onSelect(segment.id)}
            onFocus={() => onSelect(segment.id)}
            onKeyDown={(event) => moveFocus(event, index)}
          >
            <span>{segment.label}</span>
            <strong>{segment.value}</strong>
          </button>
        ))}
      </div>

      <div
        id="evidence-horizon-detail"
        role="tabpanel"
        aria-labelledby={`evidence-tab-${active.id}`}
        aria-live="polite"
      >
        <dl className="evidence-horizon-detail">
          <div>
            <dt>Source</dt>
            <dd>{active.source}</dd>
          </div>
          <div>
            <dt>Observed</dt>
            <dd>{active.observedAt}</dd>
          </div>
          <div>
            <dt>Freshness</dt>
            <dd>{active.freshness}</dd>
          </div>
          <div>
            <dt>Authority</dt>
            <dd>{active.authority}</dd>
          </div>
          <div>
            <dt>Uncertainty</dt>
            <dd>{active.uncertainty}</dd>
          </div>
        </dl>
      </div>
    </section>
  )
}

function EventTimeline({
  snapshot,
  fallback,
}: {
  snapshot: LiveSnapshot | null
  fallback: string | undefined
}) {
  const events = recentEvents(snapshot?.events ?? []).slice(0, 5)

  if (!events.length) {
    return (
      <div className="timeline-empty">
        <span>{snapshot?.observed_at ? 'No events in this report' : 'No event report yet'}</span>
        <p>{fallback ?? 'Waiting for the first observed event.'}</p>
      </div>
    )
  }

  return (
    <ol className="event-timeline">
      {events.map((event) => (
        <li key={event.id} data-tone={toneForValue(event.status)}>
          <time>{formatClockTime(event.observed_at)}</time>
          <div>
            <strong>{event.label}</strong>
            <span>
              {words(event.source)} → {words(event.target)}
            </span>
          </div>
          <b>{event.status}</b>
        </li>
      ))}
    </ol>
  )
}

function ResearchDisclosure({ widgets }: { widgets: PublicWidgets | null }) {
  const clips = widgets?.research.clips ?? []
  return (
    <details>
      <summary>
        <span>Research record</span>
        <strong>{clips.length ? `${clips.length} unverified` : NOT_OBSERVED}</strong>
      </summary>
      <div className="disclosure-body">
        {clips.length ? (
          <ol className="plain-ledger">
            {clips.slice(0, 6).map((clip) => (
              <li key={clip.id}>
                <time>{observedTime(clip.observed_at)}</time>
                <strong>{clip.title}</strong>
              </li>
            ))}
          </ol>
        ) : (
          <p>No analyst input has been published in this observation.</p>
        )}
        <p className="disclosure-note">
          Unverified advisory input · distinct-input floor:{' '}
          {formatCount(widgets?.research.policy.minimum_distinct_inputs)} ·
          single-input cap:{' '}
          {widgets ? `${Math.round(widgets.research.policy.single_input_cap * 100)}%` : NOT_OBSERVED}{' '}
          · review status: {widgets ? words(widgets.research.policy.review_status) : NOT_OBSERVED}
        </p>
      </div>
    </details>
  )
}

function SystemDisclosure({
  snapshot,
  leaseCount,
}: {
  snapshot: LiveSnapshot | null
  leaseCount: number | null
}) {
  const agents = [...(snapshot?.agents ?? [])].sort(
    (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
  )
  return (
    <details>
      <summary>
        <span>System record</span>
        <strong>
          {snapshot?.observed_at
            ? `${snapshot.nodes.length} components · ${formatCount(leaseCount)} repo holds`
            : NOT_OBSERVED}
        </strong>
      </summary>
      <div className="disclosure-body disclosure-columns">
        <div>
          <h3>Components</h3>
          <ol className="plain-ledger">
            {(snapshot?.nodes ?? []).slice(0, 8).map((node) => (
              <li key={node.id}>
                <span>{formatAge(node.freshness_s)}</span>
                <strong>{describeNode(node.id).plainName}</strong>
                <b>{node.status}</b>
              </li>
            ))}
          </ol>
          {!snapshot?.nodes.length ? <p>No component report has arrived yet.</p> : null}
        </div>
        <div>
          <h3>Recent agent state</h3>
          <ol className="plain-ledger">
            {agents.slice(0, 8).map((agent) => (
              <li key={agent.id}>
                <time>{observedTime(agent.updated_at)}</time>
                <strong>{describeAgent(agent.id).plainName}</strong>
                <b>{agent.state}</b>
              </li>
            ))}
          </ol>
          {!agents.length ? <p>No agent report has arrived yet.</p> : null}
        </div>
      </div>
    </details>
  )
}

function AssetDisclosure({
  status,
  funding,
  authority,
}: {
  status: string | undefined
  funding: string | undefined
  authority: string | undefined
}) {
  return (
    <details>
      <summary>
        <span>On-chain observation</span>
        <strong>{status ?? NOT_OBSERVED}</strong>
      </summary>
      <dl className="disclosure-body disclosure-stats">
        <div>
          <dt>Funding</dt>
          <dd>{funding ?? NOT_OBSERVED}</dd>
        </div>
        <div>
          <dt>Authority</dt>
          <dd>{authority ?? NOT_OBSERVED}</dd>
        </div>
        <div>
          <dt>Disclosure</dt>
          <dd>Banded only</dd>
        </div>
      </dl>
    </details>
  )
}

function deriveCurrentDecision({
  snapshot,
  widgets,
  execution,
  error,
  attention,
}: {
  snapshot: LiveSnapshot | null
  widgets: PublicWidgets | null
  execution: string | null
  error: string
  attention: AttentionItem[]
}): {
  verb: string
  summary: string
  pause: string
  pauseTone: EvidenceTone
  freshness: string
  freshnessTone: EvidenceTone
  nextGate: string
  nextTone: EvidenceTone
} {
  const pauseUnknown =
    widgets?.gate.pause_state === 'unknown' ||
    widgets?.gate.killswitch == null ||
    widgets == null
  const killswitch = widgets?.gate.killswitch === true
  const paused =
    killswitch ||
    ['halted', 'off', 'gated', 'paused'].includes(String(execution ?? '').toLowerCase())
  const stale = snapshot?.status === 'stale' || Boolean(error)
  const unobserved = !snapshot?.observed_at && !error

  let verb = 'HOLD'
  let summary = 'No attended action is admitted until evidence and pause truth are current.'
  if (unobserved && !widgets) {
    verb = 'REFUSE'
    summary = 'No persisted observation yet — refuse present-tense claims.'
  } else if (pauseUnknown) {
    verb = 'REFUSE'
    summary = 'Pause state unavailable — no runtime or entry claim is admitted.'
  } else if (killswitch) {
    verb = 'HOLD'
    summary = 'Kill switch engaged — entry remains ineligible until approved resume.'
  } else if (paused) {
    verb = 'HOLD'
    summary = 'Execution is held — no order path from this read-only surface.'
  } else if (stale) {
    verb = 'HOLD'
    summary = 'Evidence is stale or poll-failed — do not act on present-tense values.'
  } else if (attention.length > 0) {
    verb = 'ATTENDED ACTION'
    summary = attention[0].detail
  } else if (snapshot?.status === 'live') {
    verb = 'HOLD'
    summary = 'Observation current; no automatic action is authorized from this desk.'
  }

  const pauseLabel = pauseUnknown
    ? 'unavailable'
    : killswitch
      ? 'kill switch engaged'
      : paused
        ? words(execution) || 'paused'
        : widgets?.gate.pause_state
          ? words(widgets.gate.pause_state)
          : 'not observed'

  const freshnessLabel = error
    ? snapshot
      ? `poll failed · last report ${formatAge(snapshot.freshness_s)}`
      : 'unavailable'
    : formatAge(snapshot?.freshness_s)

  const nextGate = pauseUnknown
    ? 'Restore both pause sources before any readiness claim'
    : killswitch
      ? 'Separate approved resume transition required'
      : attention[0]?.label ??
        (snapshot?.status === 'live'
          ? 'No open gate observed on this surface'
          : 'Wait for a current admitted snapshot')

  return {
    verb,
    summary,
    pause: pauseLabel,
    pauseTone: pauseUnknown ? 'unknown' : killswitch || paused ? 'held' : 'current',
    freshness: freshnessLabel,
    freshnessTone: error || snapshot?.status === 'stale' ? 'degraded' : toneForValue(snapshot?.status),
    nextGate,
    nextTone: pauseUnknown || killswitch || attention.length ? 'held' : 'unknown',
  }
}

export function buildEvidenceSegments({
  snapshot,
  widgets,
  moss,
  fleet,
  execution,
  errors,
}: {
  snapshot: LiveSnapshot | null
  widgets: PublicWidgets | null
  moss: MossSnapshot | null
  fleet: FleetData | FleetCounts | null
  execution: string | null
  errors: { live: string; widgets: string; fleet: string; moss: string }
}): EvidenceSegment[] {
  const observed = observedTime(snapshot?.observed_at)
  const freshness = formatAge(snapshot?.freshness_s)
  const parentCurrent = snapshot?.status === 'live'
  const marketFreshness = formatAge(
    parentCurrent ? snapshot?.markets.feed_age_s : snapshot?.freshness_s,
  )
  const nestedUnavailable = snapshot?.status === 'stale' ? 'stale' : NOT_OBSERVED
  const liveTone = (value: string | null | undefined) =>
    errors.live ? 'degraded' as const : toneForValue(value)
  const fleetObservedAt =
    fleet && !isFleetCounts(fleet) ? observedTime(fleet.generated_at) : NOT_OBSERVED
  const fleetFreshness = formatAge(fleet?.snapshot_age_s)
  const fleetCurrent =
    fleet?.snapshot_age_s != null && fleet.snapshot_age_s <= RUNTIME_TTL_SECONDS
  const leaseCount = fleetCount(fleet, 'leases')
  const gateCount = fleetCount(fleet, 'gates')
  const researchObservedAt = widgets?.research.clips
    .map((clip) => clip.observed_at)
    .filter((value) => !Number.isNaN(Date.parse(value)))
    .sort((left, right) => Date.parse(right) - Date.parse(left))[0]
  const researchAge = widgets?.research.clips
    .map((clip) => clip.age_s)
    .filter((value) => Number.isFinite(value) && value >= 0)
    .sort((left, right) => left - right)[0]

  return [
    {
      id: 'snapshot',
      label: 'Snapshot',
      value: snapshot?.status ?? NOT_OBSERVED,
      source: '/api/v1/live',
      observedAt: observed,
      freshness,
      authority: 'read only',
      uncertainty: errors.live
        ? snapshot
          ? 'poll failed; value is from the last report'
          : 'poll failed; no observation'
        : snapshot
          ? 'schema-validated projection'
          : 'no observation',
      tone: liveTone(snapshot?.status),
    },
    {
      id: 'market',
      label: 'Market feed',
      value: parentCurrent ? snapshot?.markets.status ?? NOT_OBSERVED : nestedUnavailable,
      source: '/api/v1/live · markets',
      observedAt: observed,
      freshness: marketFreshness,
      authority: 'evidence only',
      uncertainty: errors.live
        ? snapshot
          ? 'poll failed; value is from the last report'
          : 'poll failed; no market observation'
        : snapshot?.markets.events_per_min == null
          ? 'rate not measured'
          : 'rate measured',
      tone: liveTone(parentCurrent ? snapshot?.markets.status : snapshot?.status),
    },
    {
      id: 'decisions',
      label: 'Decision gate',
      value: parentCurrent ? snapshot?.markets.decision_gate ?? NOT_OBSERVED : 'unknown',
      source: '/api/v1/live · desk',
      observedAt: observedTime(snapshot?.desk?.updated_at ?? snapshot?.observed_at),
      freshness,
      authority: 'execution control',
      uncertainty: errors.live
        ? snapshot?.desk
          ? 'poll failed; value is from the last report'
          : 'poll failed; no desk observation'
        : snapshot?.desk
          ? 'bounded public counts'
          : 'no desk observation',
      tone: liveTone(parentCurrent ? snapshot?.markets.decision_gate : snapshot?.status),
    },
    {
      id: 'execution',
      label: 'Execution',
      value: parentCurrent ? words(execution) : 'unknown',
      source: '/api/v1/live · execution',
      observedAt: observed,
      freshness,
      authority: ['halted', 'off', 'gated'].includes(String(execution))
        ? 'no execution permitted'
        : 'not established',
      uncertainty: errors.live
        ? execution
          ? 'poll failed; value is from the last report'
          : 'poll failed; no execution observation'
        : execution
          ? 'reported state'
          : 'no execution observation',
      tone: liveTone(parentCurrent ? execution : snapshot?.status),
    },
    {
      id: 'research',
      label: 'Research',
      value: researchObservedAt
        ? `${formatCount(widgets.research.clips.length)} unverified`
        : NOT_OBSERVED,
      source: '/api/v1/widgets · research',
      observedAt: observedTime(researchObservedAt),
      freshness: researchObservedAt ? formatAge(researchAge) : NOT_OBSERVED,
      authority: 'unverified advisory input',
      uncertainty: errors.widgets
        ? 'poll failed; value is from the last report'
        : researchObservedAt
          ? 'bounded timestamped analyst text; review and primary-source provenance are not attested'
          : 'no persisted research observation',
      tone: errors.widgets ? 'degraded' : 'unknown',
    },
    {
      id: 'fleet',
      label: 'Coordination',
      value: fleetCurrent && leaseCount != null && gateCount != null
        ? `${formatCount(leaseCount)} holds · ${formatCount(gateCount)} gates`
        : NOT_OBSERVED,
      source: '/api/fleet',
      observedAt: fleetObservedAt,
      freshness: fleetFreshness,
      authority: 'coordination only',
      uncertainty: errors.fleet
        ? 'poll failed; value is from the last report'
        : fleet?.snapshot_age_s != null
          ? !fleetCurrent
            ? 'snapshot expired; counts withdrawn'
            : isFleetCounts(fleet)
              ? 'counts-only projection; observation time absent'
              : 'sanitized fleet projection'
          : 'no timed fleet observation',
      tone: errors.fleet
        ? 'degraded'
        : fleetCurrent
          ? 'current'
          : fleet?.snapshot_age_s != null
            ? 'degraded'
            : 'unknown',
    },
    {
      id: 'moss',
      label: 'On-chain',
      value: moss?.status ?? NOT_OBSERVED,
      source: '/api/v1/moss',
      observedAt: observedTime(moss?.observed_at),
      freshness: formatAge(moss?.freshness_s),
      authority: moss?.authority ?? 'not established',
      uncertainty: errors.moss
        ? 'poll failed; value is from the last report'
        : moss
          ? 'banded public observation'
          : 'no on-chain observation',
      tone: errors.moss ? 'degraded' : toneForValue(moss?.status),
    },
  ]
}

function buildAttention({
  snapshot,
  widgets,
  execution,
  error,
  widgetsError,
  fleetError,
  mossError,
  gateCount,
}: {
  snapshot: LiveSnapshot | null
  widgets: PublicWidgets | null
  execution: string | null
  error: string
  widgetsError: string
  fleetError: string
  mossError: string
  gateCount: number | null
}): AttentionItem[] {
  const items: AttentionItem[] = []

  if (error) {
    items.push({
      label: 'Live telemetry is unavailable',
      detail: 'Keep the last observed state visible, but do not describe it in the present tense.',
      tone: 'degraded',
    })
  } else if (snapshot?.status === 'stale') {
    items.push({
      label: `Snapshot is ${formatAge(snapshot.freshness_s)}`,
      detail: 'Every value below describes that older observation.',
      tone: 'degraded',
    })
  }

  if (
    widgets?.gate.pause_state === 'unknown' ||
    widgets?.gate.killswitch == null
  ) {
    items.push({
      label: 'Pause state is unavailable',
      detail: 'No runtime or entry claim is admitted until both persisted pause sources are current.',
      tone: 'degraded',
    })
  } else if (widgets.gate.killswitch) {
    items.push({
      label: 'Kill switch is engaged',
      detail: 'Any entry path remains ineligible until a separate approved resume transition.',
      tone: 'held',
    })
  } else if (['halted', 'off', 'gated'].includes(String(execution))) {
    items.push({
      label: 'Execution is held',
      detail: 'No order path is permitted from this read-only surface.',
      tone: 'held',
    })
  }

  const blocked =
    snapshot?.status === 'live' ? snapshot.desk?.decisions.blocked : null
  if (blocked != null && blocked > 0) {
    items.push({
      label: `${blocked} ${blocked === 1 ? 'decision is' : 'decisions are'} policy-blocked`,
      detail: 'A prior approval does not override the current policy state.',
      tone: 'degraded',
    })
  }

  if (gateCount != null && gateCount > 0) {
    items.push({
      label: `${gateCount} ${gateCount === 1 ? 'gate is' : 'gates are'} open`,
      detail: 'Age and subject live in the fleet record; this page cannot clear them.',
      tone: 'held',
    })
  }

  const peripheralErrors = [widgetsError, fleetError, mossError].filter(Boolean)
  if (peripheralErrors.length) {
    items.push({
      label: `${peripheralErrors.length} supporting ${peripheralErrors.length === 1 ? 'feed is' : 'feeds are'} unavailable`,
      detail: 'The missing feeds remain unknown and do not inherit freshness from live telemetry.',
      tone: 'degraded',
    })
  }

  return items.slice(0, 4)
}

export function recentEvents(events: LiveEvent[]) {
  return [...events]
    .sort((left, right) => Date.parse(right.observed_at) - Date.parse(left.observed_at))
    .slice(0, 9)
}

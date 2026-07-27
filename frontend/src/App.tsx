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
  { href: '#attention', label: 'Attention' },
  { href: '#timeline', label: 'Changed' },
  { href: '#authority', label: 'Authority' },
  { href: '#evidence', label: 'Evidence' },
]

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
  if (!fleet) return null
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

export default function App() {
  const build = useBuildIdentity()
  const { snapshot, error, loading } = useLiveTelemetry()
  const { snapshot: moss, error: mossError } = useMossSnapshot()
  const { fleet, error: fleetError } = useFleet()
  const { widgets, error: widgetsError } = usePublicWidgets()

  const execution = snapshot?.desk?.execution ?? snapshot?.markets.execution ?? null
  const status = error ? 'unavailable' : (snapshot?.status ?? (loading ? 'warming' : 'not observed'))
  const narration = useMemo(() => (snapshot ? narrate(snapshot) : null), [snapshot])
  const gateCount = fleetCount(fleet, 'gates')
  const leaseCount = fleetCount(fleet, 'leases')

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

  const executionHeld = ['halted', 'off', 'gated'].includes(String(execution))
  const headline = executionHeld
    ? error
      ? 'Telemetry unavailable.'
      : 'Authority held.'
    : error
      ? 'Telemetry unavailable.'
      : execution
        ? `Execution ${words(execution)}.`
        : 'Awaiting observed state.'
  const executionDisplay =
    error && execution ? `${words(execution)} · last report` : words(execution)
  const attentionCount = attention.length
    ? formatCount(attention.length)
    : snapshot?.observed_at
      ? '0'
      : NOT_OBSERVED

  return (
    <div className="observatory-shell" data-execution={execution ?? 'unknown'}>
      <div className="observatory-glow" aria-hidden="true" />

      <header className="observatory-header">
        <a className="observatory-brand" href="/">
          <span aria-hidden="true">◇</span>
          Sapphire <b>Alpha</b>
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
        <section className="observatory-opening" aria-labelledby="observatory-title">
          <div>
            <p className="observatory-kicker">Decision observatory · read only</p>
            <h1 id="observatory-title">{headline}</h1>
            <p className="observatory-lede">
              What changed, what needs attention, and what is allowed to act—without
              pretending an absent measurement exists.
            </p>
          </div>

          <div className="observatory-opening-facts" aria-label="Current operating boundary">
            <div>
              <span>Execution</span>
              <strong>{executionDisplay}</strong>
            </div>
            <div>
              <span>Needs attention</span>
              <strong>{attentionCount}</strong>
            </div>
            <div>
              <span>Can act</span>
              <strong>Read and review only</strong>
            </div>
          </div>
        </section>

        <EvidenceHorizon
          segments={segments}
          active={activeEvidence}
          onSelect={setActiveId}
        />

        <div className="observatory-decision-grid">
          <section id="attention" className="attention-panel" aria-labelledby="attention-title">
            <div className="section-heading">
              <p>01 · Needs attention</p>
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
              This surface cannot place a trade, clear a halt, change a cap, or approve
              itself.
            </p>
          </section>

          <section id="timeline" className="timeline-panel" aria-labelledby="timeline-title">
            <div className="section-heading">
              <p>02 · What changed</p>
              <h2 id="timeline-title">Observed events, newest first.</h2>
            </div>
            <EventTimeline snapshot={snapshot} fallback={narration?.text} />
          </section>
        </div>

        <section id="authority" className="authority-band" aria-labelledby="authority-title">
          <div>
            <p className="observatory-kicker">03 · Authority</p>
            <h2 id="authority-title">Evidence may challenge. It may not authorize.</h2>
          </div>
          <dl>
            <div>
              <dt>Execution</dt>
              <dd>{executionHeld ? 'No execution permitted' : words(execution)}</dd>
            </div>
            <div>
              <dt>Decision gate</dt>
              <dd>{words(snapshot?.markets.decision_gate)}</dd>
            </div>
            <div>
              <dt>Research role</dt>
              <dd>{words(widgets?.research.policy.research_role)}</dd>
            </div>
            <div>
              <dt>Human gates</dt>
              <dd>{formatCount(gateCount)}</dd>
            </div>
          </dl>
        </section>

        <section id="evidence" className="evidence-ledger" aria-labelledby="evidence-title">
          <div className="section-heading section-heading--wide">
            <div>
              <p>04 · Evidence</p>
              <h2 id="evidence-title">The details stay available, not dominant.</h2>
            </div>
            <p>
              Open a ledger only when the decision needs it. The top of the page stays
              reserved for exceptions and authority.
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
        <span>Sapphire Alpha · evidence before action</span>
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
        <span>Anonymous · read only · no execution authority</span>
      </footer>
    </div>
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
    <section className="evidence-horizon" aria-labelledby="horizon-title">
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
            onClick={() => onSelect(segment.id)}
            onFocus={() => onSelect(segment.id)}
            onKeyDown={(event) => moveFocus(event, index)}
          >
            <span>{segment.label}</span>
            <strong>{segment.value}</strong>
          </button>
        ))}
      </div>

      <dl
        id="evidence-horizon-detail"
        className="evidence-horizon-detail"
        role="tabpanel"
        aria-labelledby={`evidence-tab-${active.id}`}
        aria-live="polite"
      >
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
        <strong>{clips.length ? `${clips.length} reviewed` : NOT_OBSERVED}</strong>
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
          <p>No reviewed evidence has been published in this observation.</p>
        )}
        <p className="disclosure-note">
          Minimum checks: {formatCount(widgets?.research.policy.minimum_independent_checks)} ·
          single-input cap:{' '}
          {widgets ? `${Math.round(widgets.research.policy.single_input_cap * 100)}%` : NOT_OBSERVED}
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
  const marketFreshness = formatAge(snapshot?.markets.feed_age_s)
  const liveTone = (value: string | null | undefined) =>
    errors.live ? 'degraded' as const : toneForValue(value)
  const fleetObservedAt =
    fleet && !isFleetCounts(fleet) ? observedTime(fleet.generated_at) : NOT_OBSERVED
  const fleetFreshness = formatAge(fleet?.snapshot_age_s)
  const leaseCount = fleetCount(fleet, 'leases')
  const gateCount = fleetCount(fleet, 'gates')

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
      value: snapshot?.markets.status ?? NOT_OBSERVED,
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
      tone: liveTone(snapshot?.markets.status),
    },
    {
      id: 'decisions',
      label: 'Decision gate',
      value: snapshot?.markets.decision_gate ?? NOT_OBSERVED,
      source: '/api/v1/live · desk',
      observedAt: observedTime(snapshot?.desk?.updated_at ?? snapshot?.observed_at),
      freshness,
      authority: 'human gate',
      uncertainty: errors.live
        ? snapshot?.desk
          ? 'poll failed; value is from the last report'
          : 'poll failed; no desk observation'
        : snapshot?.desk
          ? 'bounded public counts'
          : 'no desk observation',
      tone: liveTone(snapshot?.markets.decision_gate),
    },
    {
      id: 'execution',
      label: 'Execution',
      value: words(execution),
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
      tone: liveTone(execution),
    },
    {
      id: 'research',
      label: 'Research',
      value: widgets
        ? `${formatCount(widgets.research.clips.length)} reviewed`
        : NOT_OBSERVED,
      source: '/api/v1/widgets · research',
      observedAt: observedTime(widgets?.rendered_at),
      freshness: widgets?.rendered_at ? 'timestamp supplied; age not computed' : NOT_OBSERVED,
      authority: 'cannot authorize execution',
      uncertainty: errors.widgets
        ? 'poll failed; value is from the last report'
        : widgets
          ? 'bounded reviewed clips; no freshness age'
          : 'no watchboard observation',
      tone: errors.widgets ? 'degraded' : 'unknown',
    },
    {
      id: 'fleet',
      label: 'Coordination',
      value: fleet
        ? `${formatCount(leaseCount)} holds · ${formatCount(gateCount)} gates`
        : NOT_OBSERVED,
      source: '/api/fleet',
      observedAt: fleetObservedAt,
      freshness: fleetFreshness,
      authority: 'coordination only',
      uncertainty: errors.fleet
        ? 'poll failed; value is from the last report'
        : fleet
          ? isFleetCounts(fleet)
            ? 'counts-only projection; observation time absent'
            : 'sanitized fleet projection'
          : 'no fleet observation',
      tone: errors.fleet ? 'degraded' : fleet ? 'current' : 'unknown',
    },
    {
      id: 'moss',
      label: 'On-chain',
      value: moss?.status ?? NOT_OBSERVED,
      source: '/api/v1/moss',
      observedAt: observedTime(moss?.served_at),
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

  if (widgets?.gate.killswitch) {
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

  const blocked = snapshot?.desk?.decisions.blocked
  if (blocked != null && blocked > 0) {
    items.push({
      label: `${blocked} ${blocked === 1 ? 'decision is' : 'decisions are'} policy-blocked`,
      detail: 'A prior approval does not override the current policy state.',
      tone: 'degraded',
    })
  }

  if (gateCount != null && gateCount > 0) {
    items.push({
      label: `${gateCount} human ${gateCount === 1 ? 'gate is' : 'gates are'} open`,
      detail: 'These remain decisions for a person; age and subject live in the fleet record.',
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

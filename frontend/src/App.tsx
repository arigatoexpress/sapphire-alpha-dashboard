import { useMemo } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { narrate, type Narration } from '@shared/narrate'
import { describeAgent, describeNode } from '@shared/vocabulary'
import { SignalRoutes } from './components/SignalRoutes'
import { MarketAperture } from './components/MarketAperture'
import { DecisionCockpit } from './components/DecisionCockpit'
import { EvidenceWatch } from './components/EvidenceWatch'
import { LiveClock } from './components/LiveClock'
import { ShieldIcon } from './components/icons'
import {
  Count,
  Dot,
  Empty,
  Eyebrow,
  Metric,
  Notice,
  Panel,
  PanelHeading,
  StatusPill,
  toneFor,
  toneText,
} from './components/ui'
import { useLiveTelemetry } from './hooks/useLiveTelemetry'
import { useMossSnapshot } from './hooks/useMossSnapshot'
import { useFleet } from './hooks/useFleet'
import { usePublicWidgets } from './hooks/usePublicWidgets'
import {
  formatAge,
  formatClockTime,
  formatCount,
  formatRate,
  NOT_OBSERVED,
} from './desk/format'
import type {
  FleetCounts,
  FleetData,
  LiveAgent,
  LiveEvent,
  LiveSnapshot,
  MossSnapshot,
} from './types'

const SECTIONS = [
  { href: '#doctrine', label: 'Outlook' },
  { href: '#decisions', label: 'Decisions' },
  { href: '#evidence', label: 'Evidence' },
  { href: '#assets', label: 'Assets' },
  { href: '#system', label: 'System' },
]

export default function App() {
  const { snapshot, error, loading } = useLiveTelemetry()
  const { snapshot: mossSnapshot, error: mossError } = useMossSnapshot()
  const { fleet, error: fleetError } = useFleet()
  const { widgets, error: widgetsError } = usePublicWidgets()

  const status = snapshot?.status ?? (loading ? 'warming' : 'offline')
  const narration = useMemo(() => (snapshot ? narrate(snapshot) : null), [snapshot])

  return (
    <div className="min-h-screen">
      <div className="aurora" aria-hidden="true" />
      <div className="field" aria-hidden="true" />
      <div className="grain" aria-hidden="true" />

      {/* --- Top bar --------------------------------------------------- */}
      <header className="sticky top-0 z-50 border-b border-line bg-void/85 backdrop-blur-sm">
        <div className="mx-auto flex h-16 max-w-[1320px] items-center justify-between gap-6 px-5 md:px-7">
          <a
            href="/"
            className="flex shrink-0 items-center gap-2.5 font-mono text-[13px] tracking-[0.18em] text-ink uppercase"
          >
            <ShieldIcon className="w-4 text-sapphire" />
            Sapphire<span className="text-sapphire">Alpha</span>
          </a>

          <nav className="hidden items-center gap-6 lg:flex" aria-label="Sections">
            {SECTIONS.map((section) => (
              <a
                key={section.href}
                href={section.href}
                className="underline-grow font-mono text-[12px] tracking-[0.1em] text-ink-dim uppercase transition-colors hover:text-ink"
              >
                {section.label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <StatusPill status={status} pulse={status === 'live'} />
            <span className="tnum hidden font-mono text-[11px] text-ink-faint sm:inline">
              {formatAge(snapshot?.freshness_s)}
            </span>
            <span className="tnum hidden font-mono text-[11px] text-ink-faint md:inline">
              <LiveClock />
            </span>
          </div>
        </div>
      </header>

      <main id="top" className="mx-auto max-w-[1320px] px-5 pt-9 pb-24 md:px-7 md:pt-12">
        <MarketAperture snapshot={snapshot} />

        <DecisionCockpit desk={snapshot?.desk ?? null} />

        <Narrator narration={narration} />

        {(error || snapshot?.status === 'stale') && (
          <div className="mt-6 space-y-3">
            {error && (
              <Notice tone="failed">
                {error}. The last reading that did arrive is still on screen, and it is
                marked with the time it arrived.
              </Notice>
            )}
            {snapshot?.status === 'stale' && (
              <Notice tone="degraded">
                This report is {formatAge(snapshot.freshness_s)}. Everything below describes
                that moment, not this one.
              </Notice>
            )}
          </div>
        )}

        <SafetyRail snapshot={snapshot} />

        <EvidenceWatch widgets={widgets} error={widgetsError} />

        <div id="assets" className="mt-6 scroll-mt-24">
          <MossPanel snapshot={mossSnapshot} error={mossError} />
        </div>

        {/* System graph always open — this is the analysis surface, not a disclosure. */}
        <section id="system" className="mt-8 scroll-mt-24" aria-labelledby="system-heading">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="font-mono text-[11px] tracking-[0.18em] text-sapphire uppercase">
                System mesh
              </p>
              <h2
                id="system-heading"
                className="mt-2 font-display text-2xl font-semibold tracking-[-0.02em]"
              >
                Routes, agents, market feed, fleet
              </h2>
            </div>
            <em className="font-mono text-[11px] text-ink-faint not-italic">
              {snapshot?.nodes.length ?? 0} components · {snapshot?.links.length ?? 0} paths
            </em>
          </div>
          <SignalRoutes
            nodes={snapshot?.nodes ?? []}
            links={snapshot?.links ?? []}
            status={status}
          />
          <div className="mt-6">
            <FleetPanel fleet={fleet} error={fleetError} />
          </div>
          <div id="activity" className="mt-6 grid gap-6 scroll-mt-24 xl:grid-cols-3">
            <AgentPanel
              agents={snapshot?.agents ?? []}
              observed={Boolean(snapshot?.observed_at)}
            />
            <MarketPanel snapshot={snapshot} />
            <EventLedger
              events={snapshot?.events ?? []}
              observed={Boolean(snapshot?.observed_at)}
            />
          </div>
        </section>

        {/* --- Policy -------------------------------------------------- */}
        <section className="mt-12 border-t border-line pt-9">
          <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
            <div>
              <Eyebrow>Measurement contract</Eyebrow>
              <h2 className="mt-4 font-display text-2xl leading-tight font-semibold tracking-[-0.02em] text-balance">
                A number is observed, or it is absent.
              </h2>
            </div>
            <div className="space-y-4 text-base leading-relaxed text-ink-dim">
              <p>
                Every figure on this page is the figure the machines reported, at the moment
                they reported it. Nothing is delayed, rounded into an adjective, or held
                back for a different kind of visitor.
              </p>
              <p>
                Two things are deliberately absent rather than hidden behind something. The
                exact wallet balance is never published — it appears as a band, and that is
                the only number on the site treated that way. And no person, address, or
                machine name appears anywhere; the parts of the system are named for what
                they do.
              </p>
              <p>
                Where a reading does not exist, the page says so. A blank is a blank:
                round-trip times are unmeasured today because nothing is timing those hops
                yet, and they will fill in by themselves when something does.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1320px] flex-col gap-2 px-5 py-6 font-mono text-[11px] text-ink-faint sm:flex-row sm:items-center sm:justify-between md:px-7">
          <span>Sapphire Alpha · evidence before action</span>
          <span className="text-ink-dim">
            This page only reads. It cannot place a trade or change a setting.
          </span>
        </div>
      </footer>
    </div>
  )
}

/* --- Narrator ----------------------------------------------------------- */

const NARRATION_EDGE: Record<Narration['tone'], string> = {
  healthy: 'border-l-sapphire',
  degraded: 'border-l-degraded',
  stale: 'border-l-degraded',
  empty: 'border-l-line-lit',
}

/**
 * One English sentence about what is happening, from `@shared/narrate` — the
 * same function the landing page uses, so the two surfaces cannot describe the
 * same snapshot differently. It refuses to describe a stale snapshot in the
 * present tense, which is why nothing here re-words its output.
 */
function Narrator({ narration }: { narration: Narration | null }) {
  return (
    <section
      aria-label="What the system is doing right now"
      aria-live="polite"
      className={`mt-6 border-l-2 bg-raised/40 px-6 py-5 ${
        narration ? NARRATION_EDGE[narration.tone] : NARRATION_EDGE.empty
      }`}
    >
      <p className="text-base leading-relaxed text-ink text-pretty md:text-lg">
        {narration?.text ?? 'Waiting for the first report to arrive.'}
      </p>
    </section>
  )
}

/* --- Panels ------------------------------------------------------------- */

export function SafetyRail({ snapshot }: { snapshot: LiveSnapshot | null }) {
  const market = snapshot?.observed_at ? snapshot.markets : undefined
  const execution = market?.execution ?? NOT_OBSERVED
  const cells = [
    // Execution being off is the safe state, so it reads as verified.
    {
      label: 'Execution',
      value: execution,
      tone: execution === 'off' ? 'verified' : execution === NOT_OBSERVED ? 'neutral' : 'degraded',
    },
    { label: 'Decision gate', value: market?.decision_gate ?? NOT_OBSERVED },
    { label: 'Market feed', value: market?.status ?? NOT_OBSERVED },
    { label: 'Snapshot', value: snapshot?.status ?? NOT_OBSERVED },
    { label: 'Last report', value: formatAge(snapshot?.freshness_s) },
  ] as const

  return (
    <section
      aria-label="Safety and freshness rail"
      className="mt-6 grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-5"
    >
      {cells.map((cell) => {
        const tone = 'tone' in cell && cell.tone ? cell.tone : toneFor(cell.value)
        return (
          <div key={cell.label} className="bg-void px-5 py-4">
            <p className="font-mono text-[11px] tracking-[0.14em] text-ink-faint uppercase">
              {cell.label}
            </p>
            <p
              className={`mt-2 font-mono text-[12px] tracking-[0.06em] uppercase ${
                tone === 'neutral' ? 'text-ink' : toneText(tone)
              }`}
            >
              {cell.value}
            </p>
          </div>
        )
      })}
    </section>
  )
}

const COMPONENT_STATE_ORDER: Record<string, number> = {
  working: 0,
  verifying: 1,
  blocked: 2,
  idle: 3,
  offline: 4,
}

export function AgentPanel({ agents, observed }: { agents: LiveAgent[]; observed: boolean }) {
  const working = agents.filter((agent) => agent.state === 'working').length
  const ordered = [...agents].sort((left, right) => {
    const stateDelta =
      (COMPONENT_STATE_ORDER[left.state] ?? 5) -
      (COMPONENT_STATE_ORDER[right.state] ?? 5)
    return stateDelta || right.updated_at.localeCompare(left.updated_at)
  })

  return (
    <Panel label="System components">
      <PanelHeading
        eyebrow="System components"
        title="What is running"
        right={
          <Count>
            {observed ? `${working} active · ${agents.length} total` : NOT_OBSERVED}
          </Count>
        }
      />
      <div className="divide-y divide-line">
        {ordered.length ? (
          ordered.map((agent, index) => {
            const described = describeAgent(agent.id)
            return (
              <article key={`${agent.id}-${index}`} className="flex items-start gap-3 px-6 py-3.5">
                <span className="pt-1.5">
                  <Dot tone={toneFor(agent.state)} pulse={agent.state === 'working'} />
                </span>
                <div className="min-w-0 flex-1">
                  <strong className="block truncate font-display text-sm font-semibold text-ink">
                    {described.plainName}
                  </strong>
                  <p className="mt-0.5 truncate text-[13px] text-ink-dim">{agent.activity}</p>
                </div>
                <div className="shrink-0 text-right">
                  <span className="block font-mono text-[10px] text-ink-faint">
                    {agent.provider_class}
                  </span>
                  <b
                    className={`font-mono text-[10px] tracking-[0.1em] uppercase ${toneText(
                      toneFor(agent.state),
                    )}`}
                  >
                    {agent.state}
                  </b>
                </div>
              </article>
            )
          })
        ) : (
          <div className="p-6">
            <Empty
              label={
                observed
                  ? 'No system components were present in this report'
                  : 'No component report has arrived yet'
              }
            />
          </div>
        )}
      </div>
    </Panel>
  )
}

export function MarketPanel({ snapshot }: { snapshot: LiveSnapshot | null }) {
  const observed = Boolean(snapshot?.observed_at)
  const market = observed ? snapshot?.markets : undefined
  const marketNode = observed
    ? snapshot?.nodes.find((node) => node.zone === 'markets')
    : undefined

  return (
    <Panel label="Market research">
      <PanelHeading
        eyebrow="Market research"
        title={marketNode ? describeNode(marketNode.id).plainName : 'Trading desk'}
        right={<StatusPill status={market?.status} label={market?.status ?? NOT_OBSERVED} />}
      />
      <div className="px-6 py-5">
        <div className="grid grid-cols-2 gap-5">
          <Metric label="Events" value={formatRate(market?.events_per_min)} />
          <Metric label="Feed age" value={formatAge(market?.feed_age_s)} />
          <Metric label="Decision gate" value={market?.decision_gate ?? NOT_OBSERVED} />
          <Metric
            label="Execution"
            value={market?.execution ?? NOT_OBSERVED}
            tone={market?.execution === 'off' ? 'verified' : 'neutral'}
          />
        </div>

        <p className="mt-6 text-[13px] leading-relaxed text-ink-faint">
          Research forms a single probability for each binary market claim, then path bands
          for price targets. Execution is a separate gated system — caps, kill switch, designated
          capital only. No paper backtest scoreboards on this page.
        </p>
      </div>
    </Panel>
  )
}

function MossPanel({ snapshot, error }: { snapshot: MossSnapshot | null; error: string }) {
  return (
    <Panel label="MegaETH MOSS wallet observation">
      <PanelHeading
        eyebrow="Onchain assets · read only"
        title="MegaETH / MOSS"
        note="Watched through a passkey wallet that this dashboard can read and cannot spend from."
        right={<StatusPill status={snapshot?.status} label={snapshot?.status ?? NOT_OBSERVED} />}
      />
      <div className="grid gap-6 px-6 py-6 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Funding" value={snapshot?.usdm_band ?? NOT_OBSERVED} />
        <Metric label="Gas" value={snapshot?.eth_state ?? NOT_OBSERVED} />
        <Metric
          label="Observed"
          value={snapshot?.observation_freshness ?? formatAge(snapshot?.freshness_s)}
        />
        <Metric
          label="Authority"
          value={snapshot?.authority ?? NOT_OBSERVED}
          tone={snapshot?.authority ? 'verified' : 'neutral'}
        />
      </div>
      <p className="border-t border-line px-6 py-4 text-[12px] leading-relaxed text-ink-faint">
        Funding is the one figure published as a band rather than a number, and it is
        banded for everyone — this page has no view that shows the exact balance.
      </p>
      {error ? (
        <p className="border-t border-line px-6 py-4 font-mono text-[11px] text-failed">{error}</p>
      ) : null}
    </Panel>
  )
}

function isFleetCounts(fleet: FleetData | FleetCounts): fleet is FleetCounts {
  return !('counts' in fleet)
}

function FleetPanel({
  fleet,
  error,
}: {
  fleet: FleetData | FleetCounts | null
  error: string
}) {
  const ageS = fleet?.snapshot_age_s ?? null
  const stale = ageS != null && ageS >= 900
  const leaseCount = fleet ? (isFleetCounts(fleet) ? fleet.leases : fleet.counts.leases) : null
  const gateCount = fleet
    ? isFleetCounts(fleet)
      ? fleet.gates_open
      : fleet.counts.gates_open
    : null
  const totalCount =
    leaseCount === null && gateCount === null ? null : (leaseCount ?? 0) + (gateCount ?? 0)
  const detail = fleet && !isFleetCounts(fleet) ? fleet : null
  const oldestGateId = detail?.gates.length
    ? detail.gates.reduce((a, b) => (b.age_hours > a.age_hours ? b : a)).id
    : null

  return (
    <Panel id="fleet" label="Fleet coordination" className="scroll-mt-24">
      <PanelHeading
        eyebrow="Fleet coordination"
        title="Agents at work, and what is waiting for a person"
        right={
          <div className="flex items-center gap-2">
            {stale ? (
              <span className="border border-degraded/50 px-2.5 py-1 font-mono text-[11px] text-degraded">
                {formatAge(ageS)}
              </span>
            ) : null}
            <Count>{formatCount(totalCount)}</Count>
          </div>
        }
      />

      <div className="grid gap-6 border-b border-line px-6 py-6 sm:grid-cols-3">
        <Metric label="Agents holding a repo" value={formatCount(leaseCount)} />
        <Metric label="Decisions open" value={formatCount(gateCount)} />
        <Metric
          label="Counted"
          value={formatAge(ageS)}
          tone={stale ? 'degraded' : 'neutral'}
        />
      </div>

      {detail ? (
        <div className="grid gap-px bg-line md:grid-cols-2">
          <div className="bg-raised/40 px-6 py-5">
            <Eyebrow>Repos being worked on</Eyebrow>
            <div className="mt-4 space-y-px">
              {detail.leases.length ? (
                detail.leases.map((lease, index) => (
                  <article
                    key={`${lease.agent}-${index}`}
                    className="flex items-start gap-3 border-b border-line py-3 last:border-0"
                  >
                    <span className="pt-1.5">
                      <Dot tone="sapphire" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <strong className="block truncate font-display text-sm font-semibold text-ink">
                        {lease.agent}
                      </strong>
                      <p className="truncate text-[13px] text-ink-dim">
                        {lease.repo} · {lease.purpose}
                      </p>
                    </div>
                    <span className="tnum shrink-0 font-mono text-[11px] text-ink-faint">
                      until {formatClockTime(lease.expires_at)}
                    </span>
                  </article>
                ))
              ) : (
                <Empty label="No agent is holding a repo" />
              )}
            </div>
          </div>

          <div className="bg-raised/40 px-6 py-5">
            <Eyebrow>Waiting for a decision</Eyebrow>
            <div className="mt-4 space-y-px">
              {detail.gates.length ? (
                detail.gates.map((gate) => (
                  <article
                    key={gate.id}
                    className={`flex items-start gap-3 border-b border-line py-3 last:border-0 ${
                      gate.id === oldestGateId ? 'border-l-2 border-l-degraded pl-3' : ''
                    }`}
                  >
                    <span className="pt-1.5">
                      <Dot tone={gate.status === 'open' ? 'degraded' : 'neutral'} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <strong className="block truncate font-display text-sm font-semibold text-ink">
                        {gate.title}
                      </strong>
                      <p className="text-[13px] text-ink-dim">{gate.status}</p>
                    </div>
                    <span className="tnum shrink-0 font-mono text-[11px] text-ink-faint">
                      {formatAge(gate.age_hours * 3600)}
                    </span>
                  </article>
                ))
              ) : (
                <Empty label="Nothing is waiting for a decision" />
              )}
            </div>
          </div>
        </div>
      ) : (
        <p className="px-6 py-5 text-[13px] leading-relaxed text-ink-faint">
          The fleet feed carries counts. Which repo each agent is holding, and what each
          open decision is about, are not part of it.
        </p>
      )}

      {error ? (
        <p className="border-t border-line px-6 py-4 font-mono text-[11px] text-failed">
          {error}
        </p>
      ) : null}
    </Panel>
  )
}

function EventLedger({ events, observed }: { events: LiveEvent[]; observed: boolean }) {
  const reduceMotion = useReducedMotion()
  return (
    <Panel label="Evidence ledger">
      <PanelHeading eyebrow="Evidence ledger" title="What just happened" />
      <div className="divide-y divide-line">
        {/* The only entrance animation on the page, and it marks a real arrival:
            a row fades in when a new event turns up in the snapshot. */}
        <AnimatePresence initial={false}>
          {events.length ? (
            recentEvents(events)
              .map((event) => (
                <motion.article
                  key={event.id}
                  className="flex items-start gap-3 px-6 py-3.5"
                  initial={reduceMotion ? false : { opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={reduceMotion ? { duration: 0 } : undefined}
                >
                  <time className="tnum shrink-0 pt-0.5 font-mono text-[11px] text-ink-faint">
                    {formatClockTime(event.observed_at)}
                  </time>
                  <span className="pt-1.5">
                    <Dot tone={toneFor(event.status)} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <strong className="block truncate font-display text-sm font-semibold text-ink">
                      {event.label}
                    </strong>
                    <span className="block truncate font-mono text-[11px] text-ink-faint">
                      {event.source} → {event.target}
                    </span>
                  </div>
                  <b
                    className={`shrink-0 font-mono text-[10px] tracking-[0.1em] uppercase ${toneText(
                      toneFor(event.status),
                    )}`}
                  >
                    {event.status}
                  </b>
                </motion.article>
              ))
          ) : (
            <div className="p-6">
              <Empty
                label={
                  observed
                    ? 'Nothing happened during this report'
                    : 'No event report has arrived yet'
                }
              />
            </div>
          )}
        </AnimatePresence>
      </div>
    </Panel>
  )
}

export function recentEvents(events: LiveEvent[]) {
  return [...events]
    .sort((left, right) => Date.parse(right.observed_at) - Date.parse(left.observed_at))
    .slice(0, 9)
}

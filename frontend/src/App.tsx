import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { SignalLoom } from './components/SignalLoom'
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
import type {
  FleetCounts,
  FleetData,
  LiveAgent,
  LiveEvent,
  LiveSnapshot,
  MossSnapshot,
} from './types'

function formatAge(seconds: number | null): string {
  if (seconds == null) return 'not observed'
  if (seconds < 60) return `${Math.round(seconds)}s ago`
  return `${Math.round(seconds / 60)}m ago`
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return '—'
  }
}

function activityLabel(snapshot: LiveSnapshot): string {
  return (
    snapshot.summary.activity_band ??
    `${Math.round(snapshot.summary.events_per_min ?? 0)} events/min`
  )
}

const SECTIONS = [
  { href: '#loom', label: 'Loom' },
  { href: '#assets', label: 'Assets' },
  { href: '#fleet', label: 'Fleet' },
  { href: '#activity', label: 'Activity' },
]

export default function App() {
  const [creds, setCreds] = useState<{ user: string; pass: string } | null>(null)
  const [showLogin, setShowLogin] = useState(false)
  const authHeader = useMemo(
    () => (creds ? `Basic ${btoa(`${creds.user}:${creds.pass}`)}` : ''),
    [creds],
  )
  const { snapshot, error, loading, authRequired } = useLiveTelemetry(authHeader)
  const { snapshot: mossSnapshot, error: mossError } = useMossSnapshot(authHeader)
  const { fleet, error: fleetError } = useFleet(authHeader)
  const publicView = snapshot?.public_view !== false && !creds

  if ((authRequired || showLogin) && !creds) {
    return (
      <Login
        error={error}
        onCancel={snapshot ? () => setShowLogin(false) : undefined}
        onLogin={setCreds}
      />
    )
  }

  const status = snapshot?.status ?? (loading ? 'warming' : 'offline')

  return (
    <div className="min-h-screen">
      <div className="aurora" aria-hidden="true" />
      <div className="field" aria-hidden="true" />
      <div className="grain" aria-hidden="true" />

      {/* --- Top bar --------------------------------------------------- */}
      <header className="sticky top-0 z-50 border-b border-line bg-void/85 backdrop-blur-sm">
        <div className="mx-auto flex h-16 max-w-[1480px] items-center justify-between gap-6 px-6">
          <a
            href="/"
            className="flex shrink-0 items-center gap-2.5 font-mono text-[13px] tracking-[0.18em] text-ink uppercase"
            aria-label="Sapphire Alpha home"
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
              {formatAge(snapshot?.freshness_s ?? null)}
            </span>
            <span className="tnum hidden font-mono text-[11px] text-ink-faint md:inline">
              <LiveClock />
            </span>
            {publicView ? (
              <button
                className="border border-sapphire/45 px-3 py-1.5 font-mono text-[11px] tracking-[0.1em] text-sapphire uppercase transition-colors hover:bg-sapphire hover:text-void"
                onClick={() => setShowLogin(true)}
              >
                Sign in
              </button>
            ) : creds ? (
              <button
                className="border border-line-lit px-3 py-1.5 font-mono text-[11px] tracking-[0.1em] text-ink-dim uppercase transition-colors hover:border-sapphire hover:text-ink"
                onClick={() => setCreds(null)}
              >
                Public view
              </button>
            ) : null}
          </div>
        </div>
      </header>

      <main id="top" className="mx-auto max-w-[1480px] px-6 pt-14 pb-24">
        {/* --- Hero ---------------------------------------------------- */}
        <section className="grid items-end gap-10 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rise">
            <Eyebrow>Autonomous intelligence observatory</Eyebrow>
            <h1 className="mt-5 font-display text-5xl leading-[0.95] font-semibold tracking-[-0.035em] text-balance md:text-7xl">
              See the system think.
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-ink-dim text-pretty md:text-lg">
              A live, privacy-preserving view of distributed compute, agent work, market
              research, and the evidence trail connecting them.
            </p>
          </div>

          <div
            className="rise grid grid-cols-3 gap-6 border-t border-line-lit pt-6"
            style={{ animationDelay: '120ms' }}
            aria-label="Current system summary"
          >
            <Metric
              label="Active agents"
              value={String(snapshot?.summary.active_agents ?? 0)}
            />
            <Metric
              label="Activity"
              value={snapshot ? activityLabel(snapshot) : 'not observed'}
            />
            <Metric
              label="Verified today"
              value={String(snapshot?.summary.verified_today ?? 0)}
              tone={snapshot?.summary.verified_today ? 'verified' : 'neutral'}
            />
          </div>
        </section>

        {(error || snapshot?.status === 'stale') && (
          <div className="mt-10 space-y-3">
            {error && (
              <Notice tone="failed">
                {error}. Last verified observation remains visible.
              </Notice>
            )}
            {snapshot?.status === 'stale' && (
              <Notice tone="degraded">
                Telemetry is stale. Status is historical until the home projector
                reconnects.
              </Notice>
            )}
          </div>
        )}

        <SafetyRail snapshot={snapshot} />

        <div id="loom" className="mt-6 scroll-mt-24">
          <SignalLoom
            nodes={snapshot?.nodes ?? []}
            links={snapshot?.links ?? []}
            status={snapshot?.status ?? 'offline'}
          />
        </div>

        <div id="assets" className="mt-6 scroll-mt-24">
          <MossPanel snapshot={mossSnapshot} error={mossError} />
        </div>

        <div className="mt-6">
          <FleetPanel fleet={fleet} error={fleetError} />
        </div>

        <div id="activity" className="mt-6 grid gap-6 scroll-mt-24 xl:grid-cols-3">
          <AgentPanel agents={snapshot?.agents ?? []} />
          <MarketPanel snapshot={snapshot} />
          <EventLedger events={snapshot?.events ?? []} />
        </div>

        {/* --- Policy -------------------------------------------------- */}
        <section className="mt-16 border border-line-lit bg-raised/40 px-7 py-12 md:px-12">
          <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
            <div>
              <Eyebrow>Public by design</Eyebrow>
              <h2 className="mt-4 font-display text-2xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-3xl">
                Transparent outcomes. Protected infrastructure.
              </h2>
            </div>
            <p className="text-base leading-relaxed text-ink-dim">
              Every public signal is aggregated, delayed, and projected into semantic roles
              before it leaves the home mesh. The observatory shows health, flow,
              verification, and research activity — not credentials, addresses, exact
              balances, endpoints, or execution details.
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1480px] flex-col gap-2 px-6 py-6 font-mono text-[11px] text-ink-faint sm:flex-row sm:items-center sm:justify-between">
          <span>Sapphire Alpha · evidence before action</span>
          <span className="text-ink-dim">Read-only observatory · execution off</span>
        </div>
      </footer>
    </div>
  )
}

/* --- Panels ------------------------------------------------------------- */

function SafetyRail({ snapshot }: { snapshot: LiveSnapshot | null }) {
  const market = snapshot?.markets
  const execution = market?.execution ?? 'off'
  const cells = [
    // Execution being off is the safe state, so it reads as verified.
    { label: 'Execution', value: execution, tone: execution === 'off' ? 'verified' : 'degraded' },
    { label: 'Decision gate', value: market?.decision_gate ?? 'not observed' },
    { label: 'Market feed', value: market?.status ?? 'offline' },
    { label: 'Snapshot', value: snapshot?.status ?? 'offline' },
    {
      label: 'Projection',
      value: snapshot?.public_view ? 'aggregated + delayed' : 'operator detail',
    },
  ] as const

  return (
    <section
      aria-label="Safety and freshness rail"
      className="mt-10 grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-5"
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

function AgentPanel({ agents }: { agents: LiveAgent[] }) {
  return (
    <Panel label="Agent presence">
      <PanelHeading
        eyebrow="Agent presence"
        title="Work in progress"
        right={<Count>{agents.length}</Count>}
      />
      <div className="divide-y divide-line">
        {agents.length ? (
          agents.slice(0, 10).map((agent, index) => (
            <motion.article
              key={`${agent.role}-${index}`}
              className="flex items-start gap-3 px-6 py-4"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(index * 0.035, 0.25) }}
            >
              <span className="pt-1.5">
                <Dot tone={toneFor(agent.state)} pulse={agent.state === 'working'} />
              </span>
              <div className="min-w-0 flex-1">
                <strong className="block truncate font-display text-sm font-semibold text-ink">
                  {agent.role}
                </strong>
                <p className="mt-0.5 truncate text-[13px] text-ink-dim">{agent.activity}</p>
              </div>
              <div className="shrink-0 text-right">
                <span className="block font-mono text-[10px] text-ink-faint">
                  {agent.provider_class}
                </span>
                <b
                  className={`font-mono text-[10px] tracking-[0.1em] uppercase ${toneText(
                    toneFor(agent.verification),
                  )}`}
                >
                  {agent.verification}
                </b>
              </div>
            </motion.article>
          ))
        ) : (
          <div className="p-6">
            <Empty label="No agent observations yet" />
          </div>
        )}
      </div>
    </Panel>
  )
}

function MarketPanel({ snapshot }: { snapshot: LiveSnapshot | null }) {
  const market = snapshot?.markets
  const rate = market?.events_per_min ?? 0
  const band =
    market?.activity_band ??
    (rate >= 60 ? 'busy' : rate >= 10 ? 'active' : rate > 0 ? 'light' : 'quiet')
  const fill = { quiet: '8%', light: '32%', active: '64%', busy: '100%' }[band]

  return (
    <Panel label="Market research">
      <PanelHeading
        eyebrow="Market research"
        title="Robinhood Chain"
        right={<StatusPill status={market?.status ?? 'offline'} />}
      />
      <div className="px-6 py-5">
        <div className="flex items-center gap-3">
          <div className="h-1 flex-1 bg-line" role="img" aria-label={`Observed market activity is ${band}`}>
            <div
              className={`h-full transition-[width] duration-700 ${
                band === 'quiet' ? 'bg-ink-faint' : 'bg-sapphire'
              }`}
              style={{ width: fill }}
            />
          </div>
          <b className="font-mono text-[11px] tracking-[0.14em] text-ink uppercase">{band}</b>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-5">
          <Metric label="Feed" value={market?.status ?? 'offline'} />
          <Metric
            label="Activity"
            value={market?.activity_band ?? `${Math.round(rate)}/min`}
          />
          <Metric label="Paper strategies" value={String(market?.paper_strategies ?? 0)} />
          <Metric
            label="Execution"
            value={market?.execution ?? 'off'}
            tone={(market?.execution ?? 'off') === 'off' ? 'verified' : 'degraded'}
          />
        </div>

        <p className="mt-6 text-[13px] leading-relaxed text-ink-faint">
          Public-chain activity is research telemetry. Decisions remain gated; execution is
          separate and off.
        </p>
      </div>
    </Panel>
  )
}

function MossPanel({ snapshot, error }: { snapshot: MossSnapshot | null; error: string }) {
  const operator = snapshot?.public_view === false || Boolean(snapshot?.identity_masked)
  const stableValue = operator
    ? (snapshot?.usdm ?? 'not observed')
    : (snapshot?.usdm_band ?? 'not observed')
  const ethValue = operator
    ? (snapshot?.eth ?? 'not observed')
    : (snapshot?.eth_state ?? 'not observed')
  const freshness = snapshot?.observation_freshness ?? formatAge(snapshot?.freshness_s ?? null)

  return (
    <Panel label="MegaETH MOSS wallet observation">
      <PanelHeading
        eyebrow="Onchain assets · read only"
        title="MegaETH / MOSS"
        note="Hosted passkey custody with a separately projected public-state observer. No transaction authority enters Sapphire Alpha."
        right={<StatusPill status={snapshot?.status ?? 'offline'} />}
      />
      <div className="grid gap-6 px-6 py-6 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="USDm observed" value={stableValue} />
        <Metric label="ETH gas" value={ethValue} />
        <Metric label="Freshness" value={freshness} />
        <Metric label="Authority" value={snapshot?.authority ?? 'read-only'} tone="verified" />
      </div>
      {(operator && snapshot?.identity_masked) || error ? (
        <div className="border-t border-line px-6 py-4">
          {operator && snapshot?.identity_masked ? (
            <p className="font-mono text-[11px] text-ink-faint">
              Operator identity {snapshot.identity_masked} · block {snapshot.block ?? '—'}
            </p>
          ) : null}
          {error ? <p className="font-mono text-[11px] text-failed">{error}</p> : null}
        </div>
      ) : null}
    </Panel>
  )
}

function isFleetCounts(fleet: FleetData | FleetCounts): fleet is FleetCounts {
  return typeof fleet.leases === 'number'
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
  const leaseCount = fleet ? (isFleetCounts(fleet) ? fleet.leases : fleet.counts.leases) : 0
  const gateCount = fleet
    ? isFleetCounts(fleet)
      ? fleet.gates_open
      : fleet.counts.gates_open
    : 0
  const detail = fleet && !isFleetCounts(fleet) ? fleet : null
  const oldestGateId = detail?.gates.length
    ? detail.gates.reduce((a, b) => (b.age_hours > a.age_hours ? b : a)).id
    : null

  return (
    <Panel id="fleet" label="Fleet coordination" className="scroll-mt-24">
      <PanelHeading
        eyebrow="Fleet coordination"
        title="Agent leases & approval gates"
        right={
          <div className="flex items-center gap-2">
            {stale ? (
              <span className="border border-degraded/50 px-2.5 py-1 font-mono text-[11px] text-degraded">
                stale {Math.round(ageS! / 60)}m
              </span>
            ) : null}
            <Count>{leaseCount + gateCount}</Count>
          </div>
        }
      />

      <div className="grid gap-6 border-b border-line px-6 py-6 sm:grid-cols-3">
        <Metric label="Active leases" value={String(leaseCount)} />
        <Metric label="Open gates" value={String(gateCount)} />
        <Metric
          label="Snapshot"
          value={ageS != null ? formatAge(ageS) : 'not observed'}
          tone={stale ? 'degraded' : 'neutral'}
        />
      </div>

      {detail ? (
        <div className="grid gap-px bg-line md:grid-cols-2">
          <div className="bg-raised/40 px-6 py-5">
            <Eyebrow>Leases</Eyebrow>
            <div className="mt-4 space-y-px">
              {detail.leases.length ? (
                detail.leases.map((lease, index) => (
                  <article
                    key={`${lease.agent}-${index}`}
                    className="flex items-start gap-3 border-b border-line py-3 last:border-0"
                  >
                    <span className="pt-1.5">
                      <Dot tone="verified" />
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
                      until {formatTime(lease.expires_at)}
                    </span>
                  </article>
                ))
              ) : (
                <Empty label="No active leases" />
              )}
            </div>
          </div>

          <div className="bg-raised/40 px-6 py-5">
            <Eyebrow>Approval gates</Eyebrow>
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
                      {Math.round(gate.age_hours)}h
                    </span>
                  </article>
                ))
              ) : (
                <Empty label="No open gates" />
              )}
            </div>
          </div>
        </div>
      ) : (
        <p className="px-6 py-5 text-[13px] leading-relaxed text-ink-faint">
          Public projection shows aggregate coordination counts only. Operator sign-in
          reveals sanitized lease and gate detail.
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

function EventLedger({ events }: { events: LiveEvent[] }) {
  return (
    <Panel label="Evidence ledger">
      <PanelHeading eyebrow="Evidence ledger" title="Observed activity" />
      <div className="divide-y divide-line">
        <AnimatePresence initial={false}>
          {events.length ? (
            events
              .slice(-9)
              .reverse()
              .map((event) => (
                <motion.article
                  key={event.id}
                  className="flex items-start gap-3 px-6 py-3.5"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                >
                  <time className="tnum shrink-0 pt-0.5 font-mono text-[11px] text-ink-faint">
                    {formatTime(event.observed_at)}
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
              <Empty label="No verified events in this snapshot" />
            </div>
          )}
        </AnimatePresence>
      </div>
    </Panel>
  )
}

/* --- Login -------------------------------------------------------------- */

function Login({
  onLogin,
  onCancel,
  error,
}: {
  onLogin: (value: { user: string; pass: string }) => void
  onCancel?: () => void
  error: string
}) {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')

  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="aurora" aria-hidden="true" />
      <div className="field" aria-hidden="true" />
      <div className="grain" aria-hidden="true" />

      <motion.form
        className="w-full max-w-md border border-line bg-raised/60 p-8 md:p-10"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        onSubmit={(event) => {
          event.preventDefault()
          if (user && pass) onLogin({ user, pass })
        }}
      >
        <ShieldIcon className="w-6 text-sapphire" />
        <div className="mt-6">
          <Eyebrow>Sapphire Alpha</Eyebrow>
          <h1 className="mt-3 font-display text-3xl font-semibold tracking-[-0.025em]">
            Operator access
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-ink-dim">
            Authenticate for bounded operator detail. This surface remains read-only.
          </p>
        </div>

        <div className="mt-8 space-y-5">
          <label className="block">
            <span className="font-mono text-[11px] tracking-[0.14em] text-ink-faint uppercase">
              Username
            </span>
            <input
              value={user}
              onChange={(event) => setUser(event.target.value)}
              autoComplete="username"
              className="mt-2 w-full border border-line bg-sunk px-3 py-2.5 font-mono text-sm text-ink outline-none transition-colors focus:border-sapphire"
            />
          </label>
          <label className="block">
            <span className="font-mono text-[11px] tracking-[0.14em] text-ink-faint uppercase">
              Password
            </span>
            <input
              type="password"
              value={pass}
              onChange={(event) => setPass(event.target.value)}
              autoComplete="current-password"
              className="mt-2 w-full border border-line bg-sunk px-3 py-2.5 font-mono text-sm text-ink outline-none transition-colors focus:border-sapphire"
            />
          </label>
        </div>

        <button
          className="mt-8 w-full border border-sapphire bg-sapphire px-6 py-3 font-mono text-[12px] tracking-[0.14em] text-void uppercase transition-colors hover:bg-transparent hover:text-sapphire"
          type="submit"
        >
          Enter observatory
        </button>

        {error && (
          <p className="mt-4 font-mono text-[11px] text-failed">{error}</p>
        )}

        {onCancel && (
          <button
            className="underline-grow mt-5 block font-mono text-[11px] tracking-[0.1em] text-ink-dim uppercase transition-colors hover:text-ink"
            type="button"
            onClick={onCancel}
          >
            Return to public view
          </button>
        )}
      </motion.form>
    </div>
  )
}

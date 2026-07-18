import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { SignalLoom } from './components/SignalLoom'
import { LiveClock } from './components/LiveClock'
import { ShieldIcon } from './components/icons'
import { useLiveTelemetry } from './hooks/useLiveTelemetry'
import { useMossSnapshot } from './hooks/useMossSnapshot'
import { useFleet } from './hooks/useFleet'
import type { FleetCounts, FleetData, LiveAgent, LiveEvent, LiveSnapshot, MossSnapshot } from './types'

function formatAge(seconds: number | null): string {
  if (seconds == null) return 'not observed'
  if (seconds < 60) return `${Math.round(seconds)}s ago`
  return `${Math.round(seconds / 60)}m ago`
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return '—'
  }
}

function activityLabel(snapshot: LiveSnapshot): string {
  return snapshot.summary.activity_band ?? `${Math.round(snapshot.summary.events_per_min ?? 0)} events/min`
}

export default function App() {
  const [creds, setCreds] = useState<{ user: string; pass: string } | null>(null)
  const [showLogin, setShowLogin] = useState(false)
  const authHeader = useMemo(() => creds ? `Basic ${btoa(`${creds.user}:${creds.pass}`)}` : '', [creds])
  const { snapshot, error, loading, authRequired } = useLiveTelemetry(authHeader)
  const { snapshot: mossSnapshot, error: mossError } = useMossSnapshot(authHeader)
  const { fleet, error: fleetError } = useFleet(authHeader)
  const publicView = snapshot?.public_view !== false && !creds

  if ((authRequired || showLogin) && !creds) {
    return <Login error={error} onCancel={snapshot ? () => setShowLogin(false) : undefined} onLogin={setCreds} />
  }

  return (
    <div className="app-shell">
      <div className="mineral-grid" aria-hidden="true" />
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Sapphire Alpha home">
          <ShieldIcon className="brand-mark" />
          <span>SAPPHIRE <b>ALPHA</b></span>
        </a>
        <nav className="site-nav" aria-label="Sections">
          <a href="#loom">Loom</a>
          <a href="#assets">Assets</a>
          <a href="#fleet">Fleet</a>
          <a href="#activity">Activity</a>
        </nav>
        <div className="topbar-meta">
          <span className={`live-pill status-${snapshot?.status ?? 'offline'}`}><i />{snapshot?.status ?? (loading ? 'connecting' : 'offline')}</span>
          <span className="mono">{formatAge(snapshot?.freshness_s ?? null)}</span>
          <LiveClock />
          {publicView ? <button className="text-button" onClick={() => setShowLogin(true)}>Operator sign in</button> : creds ? <button className="text-button" onClick={() => setCreds(null)}>Public view</button> : null}
        </div>
      </header>

      <main id="top" className="observatory">
        <section className="hero-copy">
          <div>
            <p className="eyebrow">Autonomous intelligence observatory</p>
            <h1>See the system think.</h1>
            <p className="lede">A live, privacy-preserving view of distributed compute, agent work, market research, and the evidence trail connecting them.</p>
          </div>
          <div className="hero-stats" aria-label="Current system summary">
            <Metric label="Active agents" value={String(snapshot?.summary.active_agents ?? 0)} />
            <Metric label="System activity" value={snapshot ? activityLabel(snapshot) : 'not observed'} />
            <Metric label="Verified today" value={String(snapshot?.summary.verified_today ?? 0)} />
          </div>
        </section>

        {error && <div className="notice error-notice">{error}. Last verified observation remains visible.</div>}
        {snapshot?.status === 'stale' && <div className="notice stale-notice">Telemetry is stale. Status is historical until the home projector reconnects.</div>}

        <SafetyRail snapshot={snapshot} />
        <div id="loom" className="anchor-wrap">
          <SignalLoom nodes={snapshot?.nodes ?? []} links={snapshot?.links ?? []} status={snapshot?.status ?? 'offline'} />
        </div>
        <div id="assets" className="anchor-wrap">
          <MossPanel snapshot={mossSnapshot} error={mossError} />
        </div>
        <FleetPanel fleet={fleet} error={fleetError} />

        <div id="activity" className="lower-grid">
          <AgentPanel agents={snapshot?.agents ?? []} />
          <MarketPanel snapshot={snapshot} />
          <EventLedger events={snapshot?.events ?? []} />
        </div>

        <section className="principles">
          <div>
            <p className="eyebrow">Public by design</p>
            <h2>Transparent outcomes. Protected infrastructure.</h2>
          </div>
          <p>Every public signal is aggregated, delayed, and projected into semantic roles before it leaves the home mesh. The observatory shows health, flow, verification, and research activity—not credentials, addresses, exact balances, endpoints, or execution details.</p>
        </section>
      </main>

      <footer>
        <span>Sapphire Alpha · evidence before action</span>
        <span className="mono">READ-ONLY OBSERVATORY · EXECUTION OFF</span>
      </footer>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="hero-metric"><span>{label}</span><strong>{value}</strong></div>
}

function SafetyRail({ snapshot }: { snapshot: LiveSnapshot | null }) {
  const market = snapshot?.markets
  return (
    <section className="safety-rail" aria-label="Safety and freshness rail">
      <div><span className="rail-label">Execution</span><strong className="safe-value">{market?.execution ?? 'off'}</strong></div>
      <div><span className="rail-label">Decision gate</span><strong>{market?.decision_gate ?? 'not observed'}</strong></div>
      <div><span className="rail-label">Market feed</span><strong>{market?.status ?? 'offline'}</strong></div>
      <div><span className="rail-label">Snapshot</span><strong>{snapshot?.status ?? 'offline'}</strong></div>
      <div className="rail-policy"><span className="rail-label">Projection</span><strong>{snapshot?.public_view ? 'aggregated + delayed' : 'operator detail'}</strong></div>
    </section>
  )
}

function AgentPanel({ agents }: { agents: LiveAgent[] }) {
  return (
    <section className="data-panel agent-panel">
      <div className="section-heading"><div><p className="eyebrow">Agent presence</p><h2>Work in progress</h2></div><span className="count-badge">{agents.length}</span></div>
      <div className="agent-list">
        {agents.length ? agents.slice(0, 10).map((agent, index) => (
          <motion.article className="agent-row" key={`${agent.role}-${index}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index * .035, .25) }}>
            <span className={`presence state-${agent.state}`} />
            <div><strong>{agent.role}</strong><p>{agent.activity}</p></div>
            <div className="agent-meta"><span>{agent.provider_class}</span><b className={`verify-${agent.verification}`}>{agent.verification}</b></div>
          </motion.article>
        )) : <Empty label="No agent observations yet" />}
      </div>
    </section>
  )
}

function MarketPanel({ snapshot }: { snapshot: LiveSnapshot | null }) {
  const market = snapshot?.markets
  const band = market?.activity_band ?? ((market?.events_per_min ?? 0) >= 60 ? 'busy' : (market?.events_per_min ?? 0) >= 10 ? 'active' : (market?.events_per_min ?? 0) > 0 ? 'light' : 'quiet')
  return (
    <section className="data-panel market-panel">
      <div className="section-heading"><div><p className="eyebrow">Market research</p><h2>Robinhood Chain</h2></div><span className={`market-orb status-${market?.status ?? 'offline'}`} /></div>
      <div className={`market-meter band-${band}`} aria-label={`Observed market activity is ${band}`}>
        <span><i /></span><b>{band}</b>
      </div>
      <div className="market-grid">
        <Metric label="Feed" value={market?.status ?? 'offline'} />
        <Metric label="Activity" value={market?.activity_band ?? `${Math.round(market?.events_per_min ?? 0)}/min`} />
        <Metric label="Paper strategies" value={String(market?.paper_strategies ?? 0)} />
        <Metric label="Execution" value={market?.execution ?? 'off'} />
      </div>
      <p className="panel-caption">Public-chain activity is research telemetry. Decisions remain gated; execution is separate and off.</p>
    </section>
  )
}

function MossPanel({ snapshot, error }: { snapshot: MossSnapshot | null; error: string }) {
  const operator = snapshot?.public_view === false || Boolean(snapshot?.identity_masked)
  const stableValue = operator ? snapshot?.usdm ?? 'not observed' : snapshot?.usdm_band ?? 'not observed'
  const ethValue = operator ? snapshot?.eth ?? 'not observed' : snapshot?.eth_state ?? 'not observed'
  const freshness = snapshot?.observation_freshness ?? formatAge(snapshot?.freshness_s ?? null)
  return (
    <section className="data-panel moss-panel" aria-label="MegaETH MOSS wallet observation">
      <div className="moss-intro">
        <div>
          <p className="eyebrow">Onchain assets · read only</p>
          <h2>MegaETH / MOSS</h2>
          <p>Hosted passkey custody with a separately projected public-state observer. No transaction authority enters Sapphire Alpha.</p>
        </div>
        <span className={`moss-state status-${snapshot?.status ?? 'offline'}`}><i />{snapshot?.status ?? 'offline'}</span>
      </div>
      <div className="moss-metrics">
        <Metric label="USDm observed" value={stableValue} />
        <Metric label="ETH gas" value={ethValue} />
        <Metric label="Freshness" value={freshness} />
        <Metric label="Authority" value={snapshot?.authority ?? 'read-only'} />
        {operator && snapshot?.identity_masked ? <span className="operator-hint mono">Operator identity {snapshot.identity_masked} · block {snapshot.block ?? '—'}</span> : null}
        {error ? <span className="moss-error">{error}</span> : null}
      </div>
    </section>
  )
}

function isFleetCounts(fleet: FleetData | FleetCounts): fleet is FleetCounts {
  return typeof fleet.leases === 'number'
}

function FleetPanel({ fleet, error }: { fleet: FleetData | FleetCounts | null; error: string }) {
  const ageS = fleet?.snapshot_age_s ?? null
  const stale = ageS != null && ageS >= 900
  const leaseCount = fleet ? (isFleetCounts(fleet) ? fleet.leases : fleet.counts.leases) : 0
  const gateCount = fleet ? (isFleetCounts(fleet) ? fleet.gates_open : fleet.counts.gates_open) : 0
  const detail = fleet && !isFleetCounts(fleet) ? fleet : null
  const oldestGateId = detail?.gates.length
    ? detail.gates.reduce((a, b) => (b.age_hours > a.age_hours ? b : a)).id
    : null
  return (
    <section id="fleet" className="data-panel fleet-panel" aria-label="Fleet coordination">
      <div className="section-heading">
        <div><p className="eyebrow">Fleet coordination</p><h2>Agent leases &amp; approval gates</h2></div>
        <div className="fleet-badges">
          {stale ? <span className="fleet-stale">stale {Math.round(ageS! / 60)}m</span> : null}
          <span className="count-badge">{leaseCount + gateCount}</span>
        </div>
      </div>
      <div className="fleet-summary">
        <Metric label="Active leases" value={String(leaseCount)} />
        <Metric label="Open gates" value={String(gateCount)} />
        <Metric label="Snapshot" value={ageS != null ? formatAge(ageS) : 'not observed'} />
      </div>
      {detail ? (
        <div className="fleet-detail">
          <div>
            <p className="eyebrow">Leases</p>
            {detail.leases.length ? detail.leases.map((lease, index) => (
              <article className="fleet-row" key={`${lease.agent}-${index}`}>
                <span className="presence state-working" />
                <div><strong>{lease.agent}</strong><p>{lease.repo} · {lease.purpose}</p></div>
                <span className="mono">until {formatTime(lease.expires_at)}</span>
              </article>
            )) : <Empty label="No active leases" />}
          </div>
          <div>
            <p className="eyebrow">Approval gates</p>
            {detail.gates.length ? detail.gates.map((gate) => (
              <article className={`fleet-row${gate.id === oldestGateId ? ' fleet-oldest' : ''}`} key={gate.id}>
                <span className={`presence state-${gate.status === 'open' ? 'blocked' : 'offline'}`} />
                <div><strong>{gate.title}</strong><p>{gate.status}</p></div>
                <span className="mono">{Math.round(gate.age_hours)}h</span>
              </article>
            )) : <Empty label="No open gates" />}
          </div>
        </div>
      ) : (
        <p className="panel-caption">Public projection shows aggregate coordination counts only. Operator sign-in reveals sanitized lease and gate detail.</p>
      )}
      {error ? <span className="moss-error">{error}</span> : null}
    </section>
  )
}

function EventLedger({ events }: { events: LiveEvent[] }) {
  return (
    <section className="data-panel ledger-panel">
      <div className="section-heading"><div><p className="eyebrow">Evidence ledger</p><h2>Observed activity</h2></div></div>
      <div className="ledger-list">
        <AnimatePresence initial={false}>
          {events.length ? events.slice(-9).reverse().map((event) => (
            <motion.article key={event.id} className="ledger-row" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}>
              <time>{formatTime(event.observed_at)}</time>
              <span className={`event-mark event-${event.event_class}`} />
              <div><strong>{event.label}</strong><span>{event.source} → {event.target}</span></div>
              <b className={`event-status status-${event.status}`}>{event.status}</b>
            </motion.article>
          )) : <Empty label="No verified events in this snapshot" />}
        </AnimatePresence>
      </div>
    </section>
  )
}

function Empty({ label }: { label: string }) {
  return <div className="empty-state"><i />{label}</div>
}

function Login({ onLogin, onCancel, error }: { onLogin: (value: { user: string; pass: string }) => void; onCancel?: () => void; error: string }) {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  return (
    <div className="login-page">
      <motion.form className="login-card" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} onSubmit={(event) => { event.preventDefault(); if (user && pass) onLogin({ user, pass }) }}>
        <ShieldIcon className="login-mark" />
        <p className="eyebrow">Sapphire Alpha</p>
        <h1>Operator access</h1>
        <p>Authenticate for bounded operator detail. This surface remains read-only.</p>
        <label>Username<input value={user} onChange={(event) => setUser(event.target.value)} autoComplete="username" /></label>
        <label>Password<input type="password" value={pass} onChange={(event) => setPass(event.target.value)} autoComplete="current-password" /></label>
        <button className="primary-button" type="submit">Enter observatory</button>
        {error && <span className="form-error">{error}</span>}
        {onCancel && <button className="text-button" type="button" onClick={onCancel}>Return to public view</button>}
      </motion.form>
    </div>
  )
}

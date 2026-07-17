import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Variants } from 'framer-motion'
import type {
  WidgetData,
  Gate,
  Wallet,
  TelegramQueue,
  Signal,
  TradingView,
  BusinessHealth,
  SystemHealth,
  HealthService,
  FleetCounts,
  FleetData,
} from './types'
import { Starfield } from './components/Starfield'
import { StatusTile } from './components/StatusTile'
import { AlertStream } from './components/AlertStream'
import { LiveClock } from './components/LiveClock'
import { useTradingViewAlerts } from './hooks/useTradingViewAlerts'
import { useFleet } from './hooks/useFleet'
import { useReducedMotion } from './hooks/useReducedMotion'
import { ShieldIcon, WalletIcon, ChartIcon, TelegramIcon, ClipIcon } from './components/icons'

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, { hour12: false })
  } catch {
    return iso
  }
}

function statusClass(status: string): 'ok' | 'warn' | 'danger' {
  const s = status.toLowerCase()
  if (['ok', 'alive', 'armed', 'polling', 'running', 'healthy', 'active'].includes(s)) return 'ok'
  if (['killswitch', 'error', 'down', 'danger', 'unreachable', 'timeout'].includes(s)) return 'danger'
  return 'warn'
}

export default function App() {
  const [creds, setCreds] = useState<{ user: string; pass: string } | null>(null)
  // null = probing anonymous access; true = public read-only mode; false = auth required
  const [publicMode, setPublicMode] = useState<boolean | null>(null)
  const [showLogin, setShowLogin] = useState(false)
  const [data, setData] = useState<WidgetData | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const reducedMotion = useReducedMotion()

  const authHeader = useMemo(() => {
    if (!creds) return ''
    return 'Basic ' + btoa(`${creds.user}:${creds.pass}`)
  }, [creds])

  const fetchData = async () => {
    setLoading(true)
    setError('')
    try {
      const r = await fetch('/api/v1/widgets', {
        headers: authHeader ? { Authorization: authHeader } : {},
      })
      if (r.status === 401) {
        if (authHeader) {
          setError('Invalid credentials')
          setCreds(null)
        } else {
          // Public mode is off (or was turned off): fall back to the login screen.
          setPublicMode(false)
          setData(null)
        }
        return
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const payload: WidgetData = await r.json()
      setData(payload)
      if (!authHeader) setPublicMode(true)
    } catch (e) {
      if (!authHeader && publicMode === null) setPublicMode(false)
      setError(e instanceof Error ? e.message : 'fetch failed')
    } finally {
      setLoading(false)
    }
  }

  // Probe anonymously first; if public read-only mode is on, the dashboard
  // renders without credentials. Poll whichever mode is active.
  useEffect(() => {
    if (!creds && publicMode === false) return
    fetchData()
    const id = setInterval(fetchData, 30000)
    return () => clearInterval(id)
  }, [creds, publicMode === false])

  const isAnonymous = !creds && publicMode === true
  const showDashboard = Boolean(creds) || (isAnonymous && !showLogin)

  const { alerts: tvAlerts, error: alertsError } = useTradingViewAlerts(authHeader)
  const { fleet } = useFleet(authHeader)

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: reducedMotion ? 0 : 0.06 },
    },
  }

  const cardVariants = {
    hidden: { opacity: 0, y: 24, scale: 0.97 },
    show: {
      opacity: 1,
      y: 0,
      scale: 1,
      transition: { duration: reducedMotion ? 0 : 0.5, ease: 'easeOut' },
    },
  }

  return (
    <div className="app">
      <div className="aurora-bg" aria-hidden="true" />
      <div className="mesh-gradient" aria-hidden="true" />
      <Starfield />
      <div className="grid-overlay" aria-hidden="true" />
      <div className="grain-overlay" aria-hidden="true" />
      <AnimatePresence mode="wait">
        {publicMode === null && !creds ? (
          <div key="probe" className="login">
            <div className="muted">connecting…</div>
          </div>
        ) : !showDashboard ? (
          <Login
            key="login"
            onLogin={(c) => {
              setCreds(c)
              setShowLogin(false)
            }}
            error={error}
            onBackToPublic={publicMode === true ? () => setShowLogin(false) : undefined}
          />
        ) : (
          <motion.div
            key="dashboard"
            className="dashboard"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reducedMotion ? 0 : 0.4 }}
          >
            <header>
              <div>
                <div className="logo">
                  <ShieldIcon className="logo-icon" />
                  SAPPHIRE ALPHA
                </div>
                <div className="sub">Mission Control — autonomous trading & business control plane</div>
              </div>
              <div className="header-right">
                {isAnonymous && (
                  <a
                    className="muted"
                    href="#signin"
                    onClick={(e) => {
                      e.preventDefault()
                      setShowLogin(true)
                    }}
                  >
                    public view — sign in for operator detail
                  </a>
                )}
                <a className="muted" href="/vault/rag-map" target="_blank" rel="noreferrer">
                  vault map
                </a>
                <LiveClock />
                <span className={`status-dot ${data ? 'ok' : 'warn'} ${loading ? 'pulse' : ''}`} />
                <span className="muted">{data ? 'live' : loading ? 'loading' : 'waiting'}</span>
                <span className="muted timestamp">{data ? formatTime(data.rendered_at) : '—'}</span>
              </div>
            </header>
            <main>
              {error && <div className="error banner">{error}</div>}
              {alertsError && <div className="error banner">{alertsError}</div>}
              {data ? (
                <motion.div
                  className="mission-grid"
                  variants={containerVariants}
                  initial="hidden"
                  animate="show"
                >
                  <GateCard gate={data.gate} variants={cardVariants} />

                  <motion.div className="status-deck" variants={cardVariants}>
                    <WalletTile wallet={data.wallet} />
                    <TradingViewTile tv={data.tradingview} />
                    <TelegramTile queue={data.telegram_queue} />
                    <TdrTile feed={data.defi_report} />
                  </motion.div>

                  <TelegramQueueCard queue={data.telegram_queue} variants={cardVariants} />
                  <SignalsTape signals={data.recent_signals} variants={cardVariants} />
                  <AlertStreamCard alerts={tvAlerts} variants={cardVariants} />
                  <FleetCard fleet={fleet} variants={cardVariants} />
                  <BusinessHealthCard health={data.business_health} variants={cardVariants} />
                  <SystemHealthCard health={data.system_health} variants={cardVariants} />
                </motion.div>
              ) : (
                <div className="muted">loading dashboard…</div>
              )}
            </main>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Login({
  onLogin,
  error,
  onBackToPublic,
}: {
  onLogin: (c: { user: string; pass: string }) => void
  error: string
  onBackToPublic?: () => void
}) {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const reducedMotion = useReducedMotion()

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (user && pass) onLogin({ user, pass })
  }

  return (
    <motion.div
      className="login"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: reducedMotion ? 0 : 0.5 }}
    >
      <div className="logo">
        <ShieldIcon className="logo-icon" />
        SAPPHIRE ALPHA
      </div>
      <div className="sub">Mission Control</div>
      <form onSubmit={submit}>
        <input
          value={user}
          onChange={(e) => setUser(e.target.value)}
          placeholder="username"
          autoComplete="username"
        />
        <input
          value={pass}
          onChange={(e) => setPass(e.target.value)}
          placeholder="password"
          type="password"
          autoComplete="current-password"
        />
        <button type="submit">Enter Mission Control</button>
      </form>
      {error && <div className="error">{error}</div>}
      {onBackToPublic && (
        <a
          className="muted"
          href="#public"
          style={{ marginTop: '1rem', display: 'inline-block' }}
          onClick={(e) => {
            e.preventDefault()
            onBackToPublic()
          }}
        >
          ← back to public view
        </a>
      )}
    </motion.div>
  )
}

function GateCard({ gate, variants }: { gate: Gate; variants?: Variants }) {
  const stateClass = gate.state
  const accent =
    gate.state === 'killswitch' ? '#ff3860' : gate.state === 'armed' ? '#00d084' : '#8a94a8'

  return (
    <motion.div
      className={`card gate-hero ${stateClass}`}
      style={{ '--card-accent': accent } as React.CSSProperties}
      variants={variants}
      whileHover={{ y: -3 }}
    >
      <div className="card-glow" />
      <div className="gate-header">
        <ShieldIcon className="gate-icon" />
        <h2>Trading Gate</h2>
      </div>
      <div className="gate-status">
        <span className={`status-dot ${statusClass(gate.state)} pulse`} />
        <span className="gate-label">{gate.label}</span>
      </div>
      <div className="tag-row">
        <span className={`tag ${gate.state}`}>{gate.state}</span>
        <span className="tag">{gate.mode}</span>
        <span className={`tag ${gate.executor_alive ? 'ok' : 'warn'}`}>
          executor {gate.executor_alive ? 'alive' : 'unknown'}
        </span>
      </div>
      <div className="gate-metrics">
        <div className="metric-row">
          <span className="muted">Wallet</span>
          <span>{gate.wallet_address || '—'}</span>
        </div>
        <div className="metric-row">
          <span className="muted">Per-order cap</span>
          <span>{gate.cap_usd != null ? `$${gate.cap_usd}` : '●●●'}</span>
        </div>
        <div className="metric-row">
          <span className="muted">Updated</span>
          <span className="muted">{formatTime(gate.updated_at)}</span>
        </div>
      </div>
    </motion.div>
  )
}

function WalletTile({ wallet }: { wallet: Wallet }) {
  return (
    <StatusTile
      title="Wallet"
      status={wallet.skin_in_game ? 'ok' : 'neutral'}
      value="●●●●"
      subtitle={
        <>
          {wallet.address || '—'} · {wallet.n_open} open
        </>
      }
      icon={<WalletIcon className="tile-svg" />}
      accent="#a855f7"
      pulse={wallet.skin_in_game}
      delay={0.1}
    />
  )
}

function TradingViewTile({ tv }: { tv: TradingView }) {
  const s = statusClass(tv.status)
  return (
    <StatusTile
      title="TradingView"
      status={s}
      value={tv.status}
      subtitle={`${tv.pending_alerts} pending · ${formatTime(tv.last_ping)}`}
      icon={<ChartIcon className="tile-svg" />}
      accent="#ffb020"
      pulse={s === 'ok'}
      delay={0.2}
    />
  )
}

function TelegramTile({ queue }: { queue: TelegramQueue }) {
  const s = statusClass(queue.status)
  return (
    <StatusTile
      title="Telegram"
      status={s}
      value={queue.pending}
      subtitle={queue.status}
      icon={<TelegramIcon className="tile-svg" />}
      accent="#22d3ee"
      pulse={queue.pending > 0}
      delay={0.3}
    />
  )
}

function TdrTile({ feed }: { feed: { clips: { id: string; title: string }[]; source: string; live: boolean } }) {
  const first = feed.clips[0]
  return (
    <StatusTile
      title="TDR Pro"
      status={feed.live ? 'ok' : 'neutral'}
      value={feed.live ? 'live' : 'offline'}
      subtitle={first ? `${feed.clips.length} clips · ${first.title}` : 'no clips'}
      icon={<ClipIcon className="tile-svg" />}
      accent="#f472b6"
      pulse={feed.live}
      delay={0.4}
    />
  )
}

function TelegramQueueCard({ queue, variants }: { queue: TelegramQueue; variants?: Variants }) {
  return (
    <motion.div className="card card-tall telegram-queue" variants={variants} whileHover={{ y: -2 }}>
      <div className="card-glow" />
      <div className="queue-header">
        <div>
          <h2>Telegram Queue</h2>
          <div className="big">{queue.pending}</div>
          <div className="muted">pending approvals</div>
        </div>
        <div className="queue-status">
          <span className={`status-dot ${statusClass(queue.status)} ${queue.pending > 0 ? 'pulse' : ''}`} />
          <span>{queue.status}</span>
        </div>
      </div>
      <div className="proposal-list">
        {queue.proposals.length === 0 && <div className="muted">no recent proposals</div>}
        {queue.proposals.map((p) => (
          <div key={p.id} className="proposal-row">
            <div className="proposal-main">
              <span className="proposal-id">{p.id}</span>
              <span className="proposal-instr">{p.instrument}</span>
              <span className={`proposal-side ${p.side.toLowerCase()}`}>{p.side}</span>
              <span className="tag">{p.confidence}</span>
              <span className={`tag ${statusClass(p.status)}`}>{p.status}</span>
            </div>
            <div className="muted proposal-time">{formatTime(p.timestamp)}</div>
          </div>
        ))}
      </div>
    </motion.div>
  )
}

function SignalsTape({ signals, variants }: { signals: Signal[]; variants?: Variants }) {
  return (
    <motion.div className="card card-tall signals-tape" variants={variants} whileHover={{ y: -2 }}>
      <div className="card-glow" />
      <h2>Signals Tape</h2>
      {signals.length === 0 && <div className="muted">no recent signals</div>}
      <div className="signal-list">
        {signals.map((s) => (
          <div key={s.id} className={`signal-row ${s.side.toLowerCase()}`}>
            <span className="signal-id">{s.id}</span>
            <span className="signal-instr">{s.instrument}</span>
            <span className={`signal-side ${s.side.toLowerCase()}`}>{s.side}</span>
            {s.venue && <span className="muted">{s.venue}</span>}
            {s.confidence && <span className="tag">{s.confidence}</span>}
            <span className="muted">{formatTime(s.timestamp)}</span>
          </div>
        ))}
      </div>
    </motion.div>
  )
}

function AlertStreamCard({ alerts, variants }: { alerts: import('./types').TradingViewAlert[]; variants?: Variants }) {
  return (
    <motion.div className="card card-tall alert-stream-wrapper" variants={variants} whileHover={{ y: -2 }}>
      <AlertStream alerts={alerts} />
    </motion.div>
  )
}

const STALE_AFTER_S = 15 * 60

function staleness(ageS: number | null): { label: string; cls: 'ok' | 'warn' } {
  if (ageS == null) return { label: 'no snapshot', cls: 'warn' }
  if (ageS >= STALE_AFTER_S) return { label: `stale · ${Math.round(ageS / 60)}m old`, cls: 'warn' }
  const label = ageS < 90 ? `${Math.round(ageS)}s ago` : `${Math.round(ageS / 60)}m ago`
  return { label, cls: 'ok' }
}

function FleetCard({ fleet, variants }: { fleet: FleetData | FleetCounts | null; variants?: Variants }) {
  const countsOnly = fleet != null && 'public_view' in fleet
  const badge = staleness(fleet?.snapshot_age_s ?? null)
  const leases = !fleet || countsOnly ? [] : fleet.leases
  const gates = !fleet || countsOnly ? [] : [...fleet.gates].sort((a, b) => b.age_hours - a.age_hours)
  const leaseCount = !fleet ? 0 : countsOnly ? fleet.leases : fleet.counts.leases
  const gateCount = !fleet ? 0 : countsOnly ? fleet.gates_open : fleet.counts.gates_open

  return (
    <motion.div className="card card-wide fleet" variants={variants} whileHover={{ y: -2 }}>
      <div className="card-glow" />
      <div className="fleet-header">
        <h2>Fleet</h2>
        <span className={`tag ${badge.cls === 'warn' ? 'warn' : ''}`}>
          <span className={`status-dot ${badge.cls}`} /> snapshot {badge.label}
        </span>
      </div>
      <div className="fleet-columns">
        <div className="fleet-col">
          <div className="fleet-col-title muted">Presence · {leaseCount} agent lease{leaseCount === 1 ? '' : 's'}</div>
          {leases.length === 0 && (
            <div className="muted">{countsOnly ? 'detail is operator-only' : 'no active leases'}</div>
          )}
          {leases.map((l, i) => (
            <div key={`${l.agent}-${l.repo}-${i}`} className="fleet-row">
              <span className="tag">{l.agent}</span>
              <span className="fleet-repo">{l.repo}</span>
              <span className="muted fleet-purpose">{l.purpose || '—'}</span>
              <span className="muted">exp {formatTime(l.expires_at)}</span>
            </div>
          ))}
        </div>
        <div className="fleet-col">
          <div className="fleet-col-title muted">Inbox · {gateCount} open gate{gateCount === 1 ? '' : 's'}</div>
          {gates.length === 0 && (
            <div className="muted">{countsOnly && gateCount > 0 ? 'detail is operator-only' : 'nothing waiting on you'}</div>
          )}
          {gates.map((g, i) => (
            <div key={g.id} className={`fleet-row ${i === 0 ? 'fleet-oldest' : ''}`}>
              <span className="tag">#{g.id}</span>
              <span className="fleet-repo">{g.title}</span>
              <span className="muted">
                {g.age_hours < 1 ? `${Math.round(g.age_hours * 60)}m` : `${g.age_hours.toFixed(1)}h`} old
              </span>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

function BusinessHealthCard({ health, variants }: { health: BusinessHealth; variants?: Variants }) {
  return (
    <motion.div className="card card-wide business-health" variants={variants} whileHover={{ y: -2 }}>
      <div className="card-glow" />
      <h2>Business Health</h2>
      <div className="health-grid">
        {health.services.map((svc: HealthService) => (
          <div key={svc.name} className={`health-tile ${statusClass(svc.status)}`}>
            <div className="health-name">{svc.name}</div>
            <div className="health-status">
              <span className={`status-dot ${statusClass(svc.status)}`} />
              {svc.status}
            </div>
            {svc.http_status && <div className="muted">HTTP {svc.http_status}</div>}
            {svc.detail && <div className="muted detail">{svc.detail}</div>}
          </div>
        ))}
      </div>
      <div className="muted" style={{ marginTop: '0.75rem' }}>
        probed {formatTime(health.timestamp)}
      </div>
    </motion.div>
  )
}

function SystemHealthCard({ health, variants }: { health: SystemHealth; variants?: Variants }) {
  const entries: [string, string][] = [
    ['dashboard', health.dashboard],
    ['gate', health.gate],
    ['telegram', health.telegram],
    ['tradingview', health.tradingview],
  ]
  return (
    <motion.div className="card system-health" variants={variants} whileHover={{ y: -2 }}>
      <div className="card-glow" />
      <h2>System Health</h2>
      <div className="system-grid">
        {entries.map(([k, v]) => (
          <div key={k} className="system-tile">
            <span className={`status-dot ${statusClass(v)}`} />
            <div className="system-label">{k}</div>
            <div className="system-value">{v}</div>
          </div>
        ))}
      </div>
      <div className="muted" style={{ marginTop: '0.75rem' }}>
        {formatTime(health.timestamp)}
      </div>
    </motion.div>
  )
}

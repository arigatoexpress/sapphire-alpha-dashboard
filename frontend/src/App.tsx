import { useEffect, useMemo, useState } from 'react'

type GateState = 'killswitch' | 'armed' | 'disarmed'

interface Gate {
  state: GateState
  label: string
  armed: boolean
  killswitch: boolean
  mode: string
  wallet_address: string | null
  cap_usd: number
  executor_alive: boolean
  updated_at: string
}

interface Wallet {
  address: string | null
  deployed_usd: number
  n_open: number
  positions_count: number
  fills_count: number
  skin_in_game: boolean
  limits: Record<string, number>
  updated_at: string
}

interface TelegramQueue {
  pending: number
  gate: string
  status: string
  recent_count: number
  proposals: Proposal[]
}

interface Proposal {
  id: string
  action: string
  instrument: string
  side: string
  confidence: string
  status: string
  timestamp: string
  wallet_address?: string | null
}

interface Signal {
  id: string
  instrument: string
  side: string
  venue: string
  confidence: string
  timestamp: string
}

interface Clip {
  id: string
  title: string
  source: string
  path: string
}

interface TradingView {
  status: string
  endpoint: string
  last_ping: string
  pending_alerts: number
  recent_log: string[]
}

interface HealthService {
  name: string
  status: string
  http_status?: number
  detail?: string
}

interface BusinessHealth {
  services: HealthService[]
  timestamp: string
}

interface SystemHealth {
  dashboard: string
  gate: GateState
  telegram: string
  tradingview: string
  timestamp: string
}

interface WidgetData {
  gate: Gate
  wallet: Wallet
  telegram_queue: TelegramQueue
  recent_signals: Signal[]
  defi_report: { clips: Clip[]; source: string; live: boolean }
  tradingview: TradingView
  business_health: BusinessHealth
  system_health: SystemHealth
  rendered_at: string
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString()
  } catch {
    return iso
  }
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString()
  } catch {
    return iso
  }
}

function statusClass(status: string): string {
  const s = status.toLowerCase()
  if (['ok', 'alive', 'armed', 'polling', 'running', 'healthy', 'active'].includes(s)) return 'ok'
  if (['killswitch', 'error', 'down', 'danger', 'unreachable', 'timeout'].includes(s)) return 'danger'
  return 'warn'
}

export default function App() {
  const [creds, setCreds] = useState<{ user: string; pass: string } | null>(null)
  const [data, setData] = useState<WidgetData | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const authHeader = useMemo(() => {
    if (!creds) return ''
    return 'Basic ' + btoa(`${creds.user}:${creds.pass}`)
  }, [creds])

  const fetchData = async () => {
    if (!authHeader) return
    setLoading(true)
    setError('')
    try {
      const r = await fetch('/api/v1/widgets', {
        headers: { Authorization: authHeader },
      })
      if (r.status === 401) {
        setError('Invalid credentials')
        setCreds(null)
        return
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setData(await r.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'fetch failed')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!creds) return
    fetchData()
    const id = setInterval(fetchData, 30000)
    return () => clearInterval(id)
  }, [creds])

  if (!creds) {
    return <Login onLogin={setCreds} error={error} />
  }

  return (
    <div className="app">
      <div className="grid-overlay" />
      <header>
        <div>
          <div className="logo">SAPPHIRE ALPHA</div>
          <div className="sub">Mission Control — autonomous trading & business control plane</div>
        </div>
        <div className="header-right">
          <span className={`status-dot ${data ? 'ok' : 'warn'} ${loading ? 'pulse' : ''}`} />
          <span className="muted">{data ? 'live' : loading ? 'loading' : 'waiting'}</span>
          <span className="muted timestamp">{data ? formatTime(data.rendered_at) : '—'}</span>
        </div>
      </header>
      <main>
        {error && <div className="error" style={{ marginBottom: '1rem' }}>{error}</div>}
        {data ? (
          <div className="mission-grid">
            <GateCard gate={data.gate} />
            <WalletCard wallet={data.wallet} />
            <TelegramCard queue={data.telegram_queue} />
            <SignalsTape signals={data.recent_signals} />
            <TradingViewCard tv={data.tradingview} />
            <ClipsCard feed={data.defi_report} />
            <BusinessHealthCard health={data.business_health} />
            <SystemHealthCard health={data.system_health} />
          </div>
        ) : (
          <div className="muted">loading dashboard…</div>
        )}
      </main>
    </div>
  )
}

function Login({ onLogin, error }: { onLogin: (c: { user: string; pass: string }) => void; error: string }) {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (user && pass) onLogin({ user, pass })
  }

  return (
    <div className="login">
      <div className="logo">SAPPHIRE ALPHA</div>
      <form onSubmit={submit}>
        <input value={user} onChange={(e) => setUser(e.target.value)} placeholder="username" autoComplete="username" />
        <input value={pass} onChange={(e) => setPass(e.target.value)} placeholder="password" type="password" autoComplete="current-password" />
        <button type="submit">Enter Mission Control</button>
      </form>
      {error && <div className="error">{error}</div>}
    </div>
  )
}

function GateCard({ gate }: { gate: Gate }) {
  return (
    <div className="card card-gate">
      <div className="card-glow" />
      <h2>Trading Gate</h2>
      <div className={`gate-status ${gate.state}`}>
        <span className={`status-dot ${statusClass(gate.state)}`} />
        <span className="gate-label">{gate.label}</span>
      </div>
      <div className="tag-row">
        <span className={`tag ${gate.state}`}>{gate.state}</span>
        <span className="tag">{gate.mode}</span>
        <span className={`tag ${gate.executor_alive ? 'ok' : 'warn'}`}>
          executor {gate.executor_alive ? 'alive' : 'unknown'}
        </span>
      </div>
      <div className="metric-row">
        <span className="muted">Wallet</span>
        <span>{gate.wallet_address || '—'}</span>
      </div>
      <div className="metric-row">
        <span className="muted">Per-order cap</span>
        <span>${gate.cap_usd}</span>
      </div>
      <div className="metric-row">
        <span className="muted">Updated</span>
        <span className="muted">{formatTime(gate.updated_at)}</span>
      </div>
    </div>
  )
}

function WalletCard({ wallet }: { wallet: Wallet }) {
  return (
    <div className="card">
      <h2>Wallet & PnL</h2>
      <div className="big">${wallet.deployed_usd.toFixed(2)}</div>
      <div className="muted">deployed</div>
      <div className="metric-row" style={{ marginTop: '1rem' }}>
        <span className="muted">Address</span>
        <span>{wallet.address || '—'}</span>
      </div>
      <div className="metric-row">
        <span className="muted">Open positions</span>
        <span>{wallet.n_open}</span>
      </div>
      <div className="metric-row">
        <span className="muted">Total positions / fills</span>
        <span>{wallet.positions_count} / {wallet.fills_count}</span>
      </div>
      <div className="metric-row">
        <span className="muted">Skin in game</span>
        <span className={`status-dot ${wallet.skin_in_game ? 'ok' : 'warn'}`} />
        <span>{wallet.skin_in_game ? 'yes' : 'no'}</span>
      </div>
      {wallet.limits && Object.keys(wallet.limits).length > 0 && (
        <div className="metric-row">
          <span className="muted">Limits</span>
          <span className="muted limit-list">
            {Object.entries(wallet.limits)
              .map(([k, v]) => `${k}: ${v}`)
              .join(', ')}
          </span>
        </div>
      )}
      <div className="metric-row">
        <span className="muted">Updated</span>
        <span className="muted">{formatDate(wallet.updated_at)} {formatTime(wallet.updated_at)}</span>
      </div>
    </div>
  )
}

function TelegramCard({ queue }: { queue: TelegramQueue }) {
  return (
    <div className="card card-tall">
      <h2>Telegram Approval Queue</h2>
      <div className="queue-header">
        <div>
          <div className="big">{queue.pending}</div>
          <div className="muted">pending approvals</div>
        </div>
        <div className="queue-status">
          <span className={`status-dot ${queue.status === 'polling' ? 'ok' : 'warn'}`} />
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
    </div>
  )
}

function SignalsTape({ signals }: { signals: Signal[] }) {
  return (
    <div className="card card-tall">
      <h2>Signals Tape</h2>
      {signals.length === 0 && <div className="muted">no recent signals</div>}
      <div className="signal-list">
        {signals.map((s) => (
          <div key={s.id} className="signal-row">
            <span className="signal-id">{s.id}</span>
            <span className="signal-instr">{s.instrument}</span>
            <span className={`signal-side ${s.side.toLowerCase()}`}>{s.side}</span>
            <span className="muted">{s.venue}</span>
            <span className="tag">{s.confidence}</span>
            <span className="muted">{formatTime(s.timestamp)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function TradingViewCard({ tv }: { tv: TradingView }) {
  return (
    <div className="card">
      <h2>TradingView Webhook</h2>
      <div className="big">{tv.status}</div>
      <div className="metric-row">
        <span className="muted">Endpoint</span>
        <span className="muted endpoint" title={tv.endpoint}>{tv.endpoint}</span>
      </div>
      <div className="metric-row">
        <span className="muted">Pending alerts</span>
        <span>{tv.pending_alerts}</span>
      </div>
      <div className="metric-row">
        <span className="muted">Last ping</span>
        <span className="muted">{formatTime(tv.last_ping)}</span>
      </div>
      {tv.recent_log.length > 0 && (
        <div className="log-box">
          {tv.recent_log.map((line, i) => (
            <div key={i} className="log-line">{line}</div>
          ))}
        </div>
      )}
    </div>
  )
}

function ClipsCard({ feed }: { feed: { clips: Clip[]; source: string; live: boolean } }) {
  return (
    <div className="card card-tall">
      <h2>DeFi Report Clips</h2>
      <div className="metric-row">
        <span className="muted">source</span>
        <span className="tag">{feed.source}</span>
        <span className={`status-dot ${feed.live ? 'ok' : 'warn'}`} />
        <span className="muted">{feed.live ? 'live' : 'offline'}</span>
      </div>
      <div className="clip-list">
        {feed.clips.map((c) => (
          <div key={c.id} className="clip-row">
            <span className="clip-title">{c.title}</span>
            {c.path && <a className="clip-link" href={`file://${c.path}`} target="_blank" rel="noreferrer">open</a>}
          </div>
        ))}
      </div>
    </div>
  )
}

function BusinessHealthCard({ health }: { health: BusinessHealth }) {
  return (
    <div className="card card-wide">
      <h2>Business Health</h2>
      <div className="health-grid">
        {health.services.map((svc) => (
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
      <div className="muted" style={{ marginTop: '0.75rem' }}>probed {formatTime(health.timestamp)}</div>
    </div>
  )
}

function SystemHealthCard({ health }: { health: SystemHealth }) {
  return (
    <div className="card">
      <h2>System Health</h2>
      {Object.entries(health).map(([k, v]) => (
        <div key={k} className="metric-row">
          <span className="muted">{k}</span>
          <span className={`status-dot ${statusClass(String(v))}`} />
          <span>{String(v)}</span>
        </div>
      ))}
    </div>
  )
}

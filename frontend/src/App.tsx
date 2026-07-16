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
  updated_at: string
}

interface TelegramQueue {
  pending: number
  gate: string
  status: string
  recent_count: number
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
}

interface TradingView {
  status: string
  endpoint: string
  last_ping: string
  pending_alerts: number
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
  telegram_queue: TelegramQueue
  recent_signals: Signal[]
  defi_report: { clips: Clip[]; source: string; live: boolean }
  tradingview: TradingView
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
      <header>
        <div>
          <div className="logo">SAPPHIRE ALPHA</div>
          <div className="sub">Autonomous trading & business control plane</div>
        </div>
        <div>
          <span className={`status-dot ${data ? 'ok' : 'warn'} ${loading ? 'pulse' : ''}`} />
          <span className="muted">{data ? 'live' : loading ? 'loading' : 'waiting'}</span>
        </div>
      </header>
      <main>
        {error && <div className="error" style={{ marginBottom: '1rem' }}>{error}</div>}
        {data ? (
          <div className="grid">
            <GateCard gate={data.gate} />
            <TelegramCard queue={data.telegram_queue} />
            <SignalsCard signals={data.recent_signals} />
            <ClipsCard feed={data.defi_report} />
            <TradingViewCard tv={data.tradingview} />
            <HealthCard health={data.system_health} />
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
        <button type="submit">Enter</button>
      </form>
      {error && <div className="error">{error}</div>}
    </div>
  )
}

function GateCard({ gate }: { gate: Gate }) {
  return (
    <div className="card">
      <h2>Trading Gate</h2>
      <div className="big">{gate.label}</div>
      <div style={{ margin: '0.75rem 0' }}>
        <span className={`tag ${gate.state}`}>{gate.state}</span>
        <span className="tag" style={{ marginLeft: '0.5rem' }}>{gate.mode}</span>
      </div>
      <div className="row"><span className="muted">Wallet</span><span>{gate.wallet_address || '—'}</span></div>
      <div className="row"><span className="muted">Per-order cap</span><span>${gate.cap_usd}</span></div>
      <div className="row"><span className="muted">Updated</span><span className="muted">{formatTime(gate.updated_at)}</span></div>
    </div>
  )
}

function TelegramCard({ queue }: { queue: TelegramQueue }) {
  return (
    <div className="card">
      <h2>Telegram Approval Queue</h2>
      <div className="big">{queue.pending}</div>
      <div className="muted">pending approvals</div>
      <div className="row" style={{ marginTop: '1rem' }}>
        <span className="muted">Bot status</span>
        <span className={`status-dot ${queue.status === 'polling' ? 'ok' : 'warn'}`} />
        <span>{queue.status}</span>
      </div>
    </div>
  )
}

function SignalsCard({ signals }: { signals: Signal[] }) {
  return (
    <div className="card">
      <h2>Recent Signals</h2>
      {signals.length === 0 && <div className="muted">no recent signals</div>}
      {signals.map((s) => (
        <div key={s.id} className="row">
          <span>{s.instrument}</span>
          <span className="muted">{s.side} · {s.venue}</span>
        </div>
      ))}
    </div>
  )
}

function ClipsCard({ feed }: { feed: { clips: Clip[]; source: string; live: boolean } }) {
  return (
    <div className="card">
      <h2>DeFi Report Clips</h2>
      <div className="row">
        <span className="muted">source</span>
        <span className="tag">{feed.source}</span>
        <span className={`status-dot ${feed.live ? 'ok' : 'warn'}`} />
      </div>
      {feed.clips.map((c) => (
        <div key={c.id} className="row">
          <span>{c.title}</span>
        </div>
      ))}
    </div>
  )
}

function TradingViewCard({ tv }: { tv: TradingView }) {
  return (
    <div className="card">
      <h2>TradingView Webhook</h2>
      <div className="big">{tv.status}</div>
      <div className="row"><span className="muted">Endpoint</span><span className="muted" style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{tv.endpoint}</span></div>
      <div className="row"><span className="muted">Pending alerts</span><span>{tv.pending_alerts}</span></div>
      <div className="row"><span className="muted">Last ping</span><span className="muted">{formatTime(tv.last_ping)}</span></div>
    </div>
  )
}

function HealthCard({ health }: { health: SystemHealth }) {
  return (
    <div className="card">
      <h2>System Health</h2>
      {Object.entries(health).map(([k, v]) => (
        <div key={k} className="row">
          <span className="muted">{k}</span>
          <span className={`status-dot ${v === 'ok' || v === 'armed' || v === 'polling' ? 'ok' : v === 'killswitch' ? 'danger' : 'warn'}`} />
          <span>{String(v)}</span>
        </div>
      ))}
    </div>
  )
}

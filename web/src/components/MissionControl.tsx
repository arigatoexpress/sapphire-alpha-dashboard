'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'

type Live = {
  status?: string
  freshness_s?: number | null
  observed_at?: string | null
  desk?: {
    execution?: string | null
    leader?: string | null
    posture?: string | null
    tracks?: Array<{ strategy?: string; status?: string; live_return_pct?: number | null }>
  }
  markets?: { execution?: string | null; gpu?: string | null }
  agents?: Array<{ id?: string; state?: string; role?: string }>
  nodes?: Array<{ id?: string; status?: string; role?: string }>
  links?: Array<{ id?: string; status?: string }>
  events?: Array<{ kind?: string; summary?: string }>
  summary?: { headline?: string; detail?: string }
}

const MODULES = [
  {
    href: '/dashboard',
    kicker: '01 · Live',
    title: 'Operator desk',
    body: 'Real-time decisions, evidence, assets, fleet, and agent graph — the full instrument.',
    cta: 'Enter desk',
    accent: 'sapphire',
  },
  {
    href: '/trading/',
    kicker: '02 · Strategy',
    title: 'Free-reign rails',
    body: 'RH Agentic MCP, clip-to-cap policy, Super Heavy planner, kill-path contract.',
    cta: 'Strategy map',
    accent: 'verified',
  },
  {
    href: '/research/',
    kicker: '03 · Research',
    title: 'Multi-lens book',
    body: 'Conjecture, portfolio research, falsifiers — published reasoning without the private book.',
    cta: 'Open research',
    accent: 'ice',
  },
  {
    href: '/architecture/',
    kicker: '04 · Plant',
    title: 'Four-node plant',
    body: 'Mac control, Win GPU executor, offload VM, Cloud Run edge — separation by design.',
    cta: 'Architecture',
    accent: 'violet',
  },
  {
    href: '/onchain/',
    kicker: '05 · Settlement',
    title: 'RH Chain L2',
    body: 'On-chain legs on designated wallet. Identity never enters anonymous responses.',
    cta: 'On-chain',
    accent: 'sapphire',
  },
  {
    href: '/proof/',
    kicker: '06 · Control',
    title: 'Proof ledger',
    body: 'Observe → intent → validate → authorize → execute → reconcile. Fail-closed.',
    cta: 'Proof',
    accent: 'verified',
  },
]

function fmtAge(s: number | null | undefined) {
  if (s == null || Number.isNaN(s)) return '—'
  if (s < 60) return `${Math.round(s)}s`
  if (s < 3600) return `${Math.round(s / 60)}m`
  return `${Math.round(s / 3600)}h`
}

export default function MissionControl() {
  const [live, setLive] = useState<Live | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  const [clock, setClock] = useState('')

  useEffect(() => {
    const t = window.setInterval(() => {
      setClock(
        new Date().toLocaleString('en-US', {
          timeZone: 'America/New_York',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        }) + ' ET',
      )
    }, 1000)
    return () => window.clearInterval(t)
  }, [])

  useEffect(() => {
    let cancelled = false
    const pull = async () => {
      try {
        const res = await fetch('/api/v1/live', { cache: 'no-store' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = (await res.json()) as Live
        if (!cancelled) {
          setLive(data)
          setErr(null)
          setTick((n) => n + 1)
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : 'offline')
      }
    }
    pull()
    const id = window.setInterval(pull, 10_000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  const stats = useMemo(() => {
    const agents = live?.agents ?? []
    const nodes = live?.nodes ?? []
    const links = live?.links ?? []
    const activeAgents = agents.filter(
      (a) => a.state && !['idle', 'down', 'offline'].includes(String(a.state)),
    ).length
    const upNodes = nodes.filter((n) => n.status && n.status !== 'down').length
    return {
      agents: agents.length,
      activeAgents,
      nodes: nodes.length,
      upNodes,
      links: links.length,
      exec: live?.desk?.execution ?? live?.markets?.execution ?? '—',
      posture: live?.desk?.posture ?? '—',
      status: live?.status ?? 'warming',
      tracks: live?.desk?.tracks ?? [],
      events: (live?.events ?? []).slice(0, 6),
    }
  }, [live])

  const meshNodes = useMemo(() => {
    const base = [
      { id: 'sense', x: 12, y: 42, label: 'SENSE', sub: 'VPIN · TV' },
      { id: 'plan', x: 32, y: 28, label: 'PLAN', sub: 'Super Heavy' },
      { id: 'policy', x: 52, y: 48, label: 'POLICY', sub: 'Free-reign' },
      { id: 'exec', x: 72, y: 30, label: 'EXEC', sub: 'RH · L2' },
      { id: 'gov', x: 90, y: 50, label: 'GOV', sub: 'Fence' },
      { id: 'mac', x: 28, y: 72, label: 'MAC', sub: 'Control' },
      { id: 'win', x: 58, y: 78, label: 'WIN', sub: 'GPU plant' },
      { id: 'edge', x: 82, y: 72, label: 'EDGE', sub: 'Cloud Run' },
    ]
    return base
  }, [])

  return (
    <div className="mc-root">
      <div className="mc-bg" aria-hidden="true" />
      <div className="mc-scan" aria-hidden="true" />

      {/* Top mission bar */}
      <div className="mc-topbar">
        <div className="mc-brand">
          <span className="mc-dot mc-dot--live" />
          <span>SAPPHIRE ALPHA · MISSION CONTROL</span>
        </div>
        <div className="mc-topmeta">
          <span className={stats.status === 'live' ? 'text-verified' : 'text-degraded'}>
            {stats.status.toUpperCase()}
          </span>
          <span className="mc-sep">·</span>
          <span>AGE {fmtAge(live?.freshness_s)}</span>
          <span className="mc-sep">·</span>
          <span className="tnum">{clock || '—'}</span>
          <span className="mc-sep">·</span>
          <span className="tnum">POLL {tick}</span>
        </div>
      </div>

      <div className="mc-shell">
        {/* Hero + KPIs — keep "Autonomous capital" / "Command desk" for RTH health gate */}
        <header className="mc-hero" aria-label="Command desk">
          <div>
            <p className="mc-kicker">Self-sovereign trading plant · Command desk</p>
            <h1>
              Autonomous capital.
              <br />
              <em>Full visibility.</em>
            </h1>
            <p className="mc-lede">
              One console for free-reign agentic execution, Super Heavy orchestration, VPIN risk,
              L2 settlement, and research — built to run on designated capital and prove its own
              claims.
            </p>
            <div className="mc-cta-row">
              <Link href="/dashboard" className="mc-btn mc-btn--primary">
                Open live desk →
              </Link>
              <Link href="/trading/" className="mc-btn">
                Strategy rails
              </Link>
              <Link href="/research/" className="mc-btn">
                Research
              </Link>
            </div>
          </div>

          <div className="mc-kpi-grid">
            {[
              { l: 'Agents', v: String(stats.agents), s: `${stats.activeAgents} active` },
              { l: 'Nodes', v: String(stats.nodes), s: `${stats.upNodes} up` },
              { l: 'Links', v: String(stats.links), s: 'mesh' },
              { l: 'Desk exec', v: String(stats.exec), s: String(stats.posture) },
            ].map((k) => (
              <div key={k.l} className="mc-kpi">
                <span>{k.l}</span>
                <strong className="tnum">{k.v}</strong>
                <small>{k.s}</small>
              </div>
            ))}
          </div>
        </header>

        {/* Visual plant mesh */}
        <section className="mc-panel mc-mesh-panel" aria-label="Plant mesh">
          <div className="mc-panel-head">
            <span>PLANT MESH</span>
            <span className="mc-muted">
              {err ? `feed · ${err}` : live?.summary?.headline || 'live architecture projection'}
            </span>
          </div>
          <div className="mc-mesh-wrap">
            <svg viewBox="0 0 100 100" className="mc-mesh" role="img" aria-label="Plant network">
              <defs>
                <linearGradient id="mcLine" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#6d8cff" stopOpacity="0.2" />
                  <stop offset="50%" stopColor="#6d8cff" stopOpacity="0.95" />
                  <stop offset="100%" stopColor="#45e08d" stopOpacity="0.7" />
                </linearGradient>
                <filter id="mcGlow">
                  <feGaussianBlur stdDeviation="1.2" result="b" />
                  <feMerge>
                    <feMergeNode in="b" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              {/* links */}
              <path
                d="M12 42 L32 28 L52 48 L72 30 L90 50"
                fill="none"
                stroke="url(#mcLine)"
                strokeWidth="0.45"
                className="mc-flow"
              />
              <path
                d="M32 28 L28 72 M52 48 L58 78 M72 30 L82 72"
                fill="none"
                stroke="#2a3552"
                strokeWidth="0.35"
              />
              <path
                d="M28 72 L58 78 L82 72"
                fill="none"
                stroke="#2a3552"
                strokeWidth="0.35"
              />
              {meshNodes.map((n) => (
                <g key={n.id} transform={`translate(${n.x} ${n.y})`}>
                  <circle r="3.2" className="mc-node-ring" filter="url(#mcGlow)" />
                  <circle r="1.1" className="mc-node-core" />
                  <text y="-5" textAnchor="middle" className="mc-node-label">
                    {n.label}
                  </text>
                  <text y="7.5" textAnchor="middle" className="mc-node-sub">
                    {n.sub}
                  </text>
                </g>
              ))}
            </svg>
          </div>
        </section>

        {/* Tracks + event tape */}
        <div className="mc-split">
          <section className="mc-panel">
            <div className="mc-panel-head">
              <span>STRATEGY TRACKS</span>
              <span className="mc-muted">desk projection</span>
            </div>
            <div className="mc-tracks">
              {stats.tracks.length === 0 && (
                <p className="mc-empty">No track rows in public projection yet.</p>
              )}
              {stats.tracks.slice(0, 8).map((t, i) => (
                <div key={`${t.strategy}-${i}`} className="mc-track">
                  <div>
                    <strong>{t.strategy || 'track'}</strong>
                    <span>{t.status || '—'}</span>
                  </div>
                  <em className="tnum">
                    {t.live_return_pct == null
                      ? '—'
                      : `${t.live_return_pct > 0 ? '+' : ''}${t.live_return_pct.toFixed(1)}%`}
                  </em>
                </div>
              ))}
            </div>
          </section>

          <section className="mc-panel">
            <div className="mc-panel-head">
              <span>EVENT TAPE</span>
              <span className="mc-muted">recent plant events</span>
            </div>
            <div className="mc-tape">
              {stats.events.length === 0 && (
                <p className="mc-empty">Waiting for signed events…</p>
              )}
              {stats.events.map((e, i) => (
                <div key={i} className="mc-tape-row">
                  <span>{e.kind || 'event'}</span>
                  <p>{e.summary || '—'}</p>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* Module grid — the place to analyze everything */}
        <section className="mc-modules" aria-labelledby="modules-title">
          <div className="mc-section-title">
            <p className="mc-kicker">Navigate the system</p>
            <h2 id="modules-title">Where to look. What each surface is for.</h2>
          </div>
          <div className="mc-module-grid">
            {MODULES.map((m) => (
              <Link key={m.href} href={m.href} className={`mc-module mc-module--${m.accent}`}>
                <span className="mc-module-kicker">{m.kicker}</span>
                <h3>{m.title}</h3>
                <p>{m.body}</p>
                <span className="mc-module-cta">{m.cta} →</span>
              </Link>
            ))}
          </div>
        </section>

        {/* Rails strip */}
        <section className="mc-rails">
          {[
            ['RH Agentic MCP', 'Equities + single-leg options'],
            ['Free-reign easy', 'Account-scale auto-approve'],
            ['MOSS MegaETH', '20 USDm/day transfer-only'],
            ['Super Heavy', 'Planner · never places'],
            ['VPIN / TA / TV', 'Advisory flow + alerts'],
            ['Trade journal', 'Every fill + prediction'],
          ].map(([t, d]) => (
            <div key={t} className="mc-rail">
              <strong>{t}</strong>
              <span>{d}</span>
            </div>
          ))}
        </section>

        {/* Research epistemics */}
        <section className="mc-panel" style={{ marginTop: '1.25rem' }}>
          <div className="mc-panel-head">
            <span>RESEARCH CONTRACT</span>
            <Link href="/research/" className="mc-muted">
              open research →
            </Link>
          </div>
          <div style={{ padding: '1rem 1.1rem', display: 'grid', gap: '0.85rem' }}>
            <p style={{ margin: 0, color: 'var(--color-ink-dim)', fontSize: '0.95rem', lineHeight: 1.55 }}>
              <strong style={{ color: 'var(--color-ink)' }}>Events</strong> (BTC bottom in?
              recession? cycle intact?) get <em>one probability as of now</em>.{' '}
              <strong style={{ color: 'var(--color-ink)' }}>Path forecasts</strong> use short /
              medium / long for price targets, growth, and trends — not for event odds.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              <Link href="/research/conjecture-2026-07-27/" className="mc-btn">
                Latest opinions
              </Link>
              <Link href="/research/portfolio-research-2026-07-27/" className="mc-btn">
                Portfolio multi-lens
              </Link>
              <Link href="/dashboard" className="mc-btn mc-btn--primary">
                Live desk
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

'use client'

import { useEffect, useMemo, useState } from 'react'

type LiveSlice = {
  status?: string
  freshness_s?: number | null
  desk?: {
    execution?: string | null
    leader?: string | null
    posture?: string | null
  }
  markets?: {
    execution?: string | null
    gpu?: string | null
  }
  agents?: Array<{ id?: string; state?: string }>
  nodes?: Array<{ id?: string; status?: string }>
  summary?: { headline?: string }
}

const RAILS = [
  {
    id: 'rh-agentic',
    name: 'RH Agentic MCP',
    role: 'Brokerage equities + single-leg options',
    host: 'Mac gate · Win executor',
    tone: 'verified' as const,
  },
  {
    id: 'free-reign',
    name: 'Free-reign easy',
    role: 'Auto-approve under account-scale caps',
    host: 'Policy · clip-to-cap',
    tone: 'sapphire' as const,
  },
  {
    id: 'l2',
    name: 'RH Chain L2',
    role: 'On-chain settlement · designated wallet',
    host: 'Windows plant',
    tone: 'ice' as const,
  },
  {
    id: 'super-heavy',
    name: 'Super Heavy',
    role: 'System orchestrator · plans only',
    host: 'Grok → Nemotron',
    tone: 'sapphire' as const,
  },
  {
    id: 'vpin',
    name: 'VPIN / TA / TV',
    role: 'Flow toxicity · alerts · webhooks',
    host: 'RTX 5070 Ti',
    tone: 'ice' as const,
  },
  {
    id: 'desk',
    name: 'Sovereign desk',
    role: 'Thesis · APEX · paper tracks',
    host: 'Schtasks plant',
    tone: 'verified' as const,
  },
]

const STACK = [
  { layer: 'Sense', items: ['VPIN tape', 'TA alerts', 'TV webhooks', 'Research corpus'] },
  { layer: 'Decide', items: ['Super Heavy', 'Nemotron council', 'Thesis engine', 'Free-reign policy'] },
  { layer: 'Act', items: ['RH Agentic MCP', 'Brokerage pickle', 'L2 wallet', 'Executor'] },
  { layer: 'Govern', items: ['Wallet fence', 'Kill switch', 'Per-venue slots', 'Daily envelope'] },
]

function toneClass(tone: 'verified' | 'sapphire' | 'ice' | 'degraded' | 'failed') {
  switch (tone) {
    case 'verified':
      return 'text-verified border-verified/40 bg-verified/5'
    case 'sapphire':
      return 'text-sapphire border-sapphire/40 bg-sapphire/5'
    case 'ice':
      return 'text-ice border-ice/35 bg-ice/5'
    case 'degraded':
      return 'text-degraded border-degraded/40 bg-degraded/5'
    case 'failed':
      return 'text-failed border-failed/40 bg-failed/5'
  }
}

export default function CommandDesk() {
  const [live, setLive] = useState<LiveSlice | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    const pull = async () => {
      try {
        const res = await fetch('/api/v1/live', { cache: 'no-store' })
        if (!res.ok) throw new Error(`live ${res.status}`)
        const data = (await res.json()) as LiveSlice
        if (!cancelled) {
          setLive(data)
          setErr(null)
          setTick((t) => t + 1)
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : 'offline')
      }
    }
    pull()
    const id = window.setInterval(pull, 12_000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  const plant = useMemo(() => {
    const agents = live?.agents?.length ?? 0
    const nodes = live?.nodes?.length ?? 0
    const liveAgents =
      live?.agents?.filter((a) => a.state && a.state !== 'idle' && a.state !== 'down').length ?? 0
    const exec = live?.desk?.execution ?? live?.markets?.execution ?? '—'
    return { agents, nodes, liveAgents, exec, status: live?.status ?? 'warming' }
  }, [live])

  return (
    <section className="relative overflow-hidden border-b border-line" aria-label="Command desk">
      <div className="pointer-events-none absolute inset-0 desk-glow" aria-hidden="true" />
      <div className="pointer-events-none absolute inset-0 desk-grid" aria-hidden="true" />

      <div className="relative mx-auto max-w-[1440px] px-5 pb-16 pt-10 md:px-8 md:pt-14">
        {/* Hero */}
        <div className="grid gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:items-end">
          <div>
            <p className="font-mono text-[11px] tracking-[0.22em] text-sapphire uppercase">
              Sovereign trading plant
            </p>
            <h1 className="mt-4 max-w-3xl font-display text-5xl leading-[0.95] font-semibold tracking-[-0.03em] text-balance md:text-7xl">
              Autonomous capital.
              <span className="block text-sapphire">Instrument-grade control.</span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-dim text-pretty">
              One surface for the full stack: Robinhood Agentic free-reign, Super Heavy
              orchestration, VPIN risk, L2 settlement, and a fail-closed kill path — built to
              trade, manage risk, and compound on designated rails.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a
                href="/dashboard"
                className="border border-sapphire bg-sapphire px-5 py-3 font-mono text-[11px] tracking-[0.14em] text-void uppercase transition-colors hover:bg-transparent hover:text-sapphire"
              >
                Open live desk →
              </a>
              <a
                href="/trading/"
                className="border border-line-lit px-5 py-3 font-mono text-[11px] tracking-[0.14em] text-ink-dim uppercase transition-colors hover:border-sapphire hover:text-ink"
              >
                Strategy rails
              </a>
              <a
                href="/research/"
                className="border border-line-lit px-5 py-3 font-mono text-[11px] tracking-[0.14em] text-ink-dim uppercase transition-colors hover:border-sapphire hover:text-ink"
              >
                Research
              </a>
            </div>
          </div>

          {/* Live telemetry strip */}
          <div className="border border-line bg-raised/80 p-5 md:p-6">
            <div className="flex items-center justify-between gap-3">
              <p className="font-mono text-[10px] tracking-[0.18em] text-ink-faint uppercase">
                Plant telemetry
              </p>
              <span
                className={`inline-flex items-center gap-1.5 font-mono text-[10px] tracking-[0.14em] uppercase ${
                  plant.status === 'live' ? 'text-verified' : 'text-degraded'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 ${plant.status === 'live' ? 'bg-verified pulse-verified' : 'bg-degraded'}`}
                />
                {plant.status}
              </span>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                { k: 'Agents', v: String(plant.agents) },
                { k: 'Active', v: String(plant.liveAgents) },
                { k: 'Nodes', v: String(plant.nodes) },
                { k: 'Exec', v: String(plant.exec) },
              ].map((m) => (
                <div key={m.k} className="border border-line bg-void px-3 py-3">
                  <p className="font-mono text-[10px] tracking-[0.14em] text-ink-faint uppercase">
                    {m.k}
                  </p>
                  <p className="tnum mt-2 font-display text-xl font-semibold tracking-tight text-ink">
                    {m.v}
                  </p>
                </div>
              ))}
            </div>
            <p className="mt-4 font-mono text-[11px] leading-relaxed text-ink-faint">
              {err
                ? `Feed: ${err}`
                : live?.summary?.headline ||
                  `Freshness ${live?.freshness_s != null ? `${Math.round(live.freshness_s)}s` : '—'} · poll #${tick}`}
            </p>
          </div>
        </div>

        {/* Architecture SVG */}
        <div className="mt-14 border border-line bg-void">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
            <p className="font-mono text-[11px] tracking-[0.16em] text-sapphire uppercase">
              Signal → decision → fill
            </p>
            <p className="font-mono text-[10px] tracking-[0.12em] text-ink-faint uppercase">
              Designated rails only
            </p>
          </div>
          <div className="overflow-x-auto p-4 md:p-8">
            <svg
              viewBox="0 0 960 220"
              className="mx-auto h-auto w-full min-w-[640px] max-w-5xl"
              role="img"
              aria-label="Plant architecture flow"
            >
              <defs>
                <linearGradient id="flowGrad" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#6d8cff" stopOpacity="0.15" />
                  <stop offset="50%" stopColor="#6d8cff" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#45e08d" stopOpacity="0.8" />
                </linearGradient>
              </defs>
              {/* backbone */}
              <path
                d="M80 110 H880"
                stroke="url(#flowGrad)"
                strokeWidth="2"
                fill="none"
                className="desk-flow-line"
              />
              {[
                { x: 80, label: 'SENSE', sub: 'VPIN · TV · TA' },
                { x: 300, label: 'PLAN', sub: 'Super Heavy' },
                { x: 520, label: 'POLICY', sub: 'Free-reign' },
                { x: 740, label: 'EXECUTE', sub: 'RH · L2' },
                { x: 880, label: 'GOVERN', sub: 'Fence · Kill' },
              ].map((n) => (
                <g key={n.label} transform={`translate(${n.x}, 110)`}>
                  <circle r="10" className="fill-void stroke-sapphire" strokeWidth="1.5" />
                  <circle r="3" className="fill-sapphire" />
                  <text
                    y="-28"
                    textAnchor="middle"
                    className="fill-ink"
                    style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.12em' }}
                  >
                    {n.label}
                  </text>
                  <text
                    y="32"
                    textAnchor="middle"
                    className="fill-ink-faint"
                    style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}
                  >
                    {n.sub}
                  </text>
                </g>
              ))}
              {/* side hosts */}
              <rect x="220" y="150" width="120" height="36" className="fill-raised stroke-line" />
              <text
                x="280"
                y="172"
                textAnchor="middle"
                className="fill-ink-dim"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}
              >
                Mac control
              </text>
              <rect x="520" y="150" width="140" height="36" className="fill-raised stroke-line" />
              <text
                x="590"
                y="172"
                textAnchor="middle"
                className="fill-ink-dim"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}
              >
                Win GPU plant
              </text>
            </svg>
          </div>
        </div>

        {/* Rails grid */}
        <div className="mt-10">
          <div className="mb-5 flex items-end justify-between gap-4">
            <div>
              <p className="font-mono text-[11px] tracking-[0.18em] text-sapphire uppercase">
                Live rails
              </p>
              <h2 className="mt-2 font-display text-3xl font-semibold tracking-[-0.02em] md:text-4xl">
                Everything that can move capital.
              </h2>
            </div>
          </div>
          <div className="grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
            {RAILS.map((rail) => (
              <article key={rail.id} className="bg-void p-6 transition-colors hover:bg-raised">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-display text-xl font-semibold tracking-[-0.015em]">
                    {rail.name}
                  </h3>
                  <span
                    className={`shrink-0 border px-2 py-0.5 font-mono text-[10px] tracking-[0.12em] uppercase ${toneClass(rail.tone)}`}
                  >
                    live
                  </span>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-ink-dim">{rail.role}</p>
                <p className="mt-4 font-mono text-[11px] tracking-[0.08em] text-ink-faint">
                  {rail.host}
                </p>
              </article>
            ))}
          </div>
        </div>

        {/* Stack layers */}
        <div className="mt-10 grid gap-px border border-line bg-line md:grid-cols-4">
          {STACK.map((s) => (
            <div key={s.layer} className="bg-void p-6">
              <p className="font-mono text-[10px] tracking-[0.18em] text-sapphire uppercase">
                {s.layer}
              </p>
              <ul className="mt-4 space-y-2">
                {s.items.map((item) => (
                  <li
                    key={item}
                    className="border-l border-line-lit pl-3 text-sm leading-relaxed text-ink-dim"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

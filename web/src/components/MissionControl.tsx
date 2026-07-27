'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'

type Live = {
  status?: string
  freshness_s?: number | null
  desk?: {
    execution?: string | null
    posture?: string | null
    tracks?: Array<{ strategy?: string; status?: string; live_return_pct?: number | null }>
  }
  markets?: { execution?: string | null }
  agents?: Array<{ id?: string; state?: string }>
  nodes?: Array<{ id?: string; status?: string }>
  summary?: { headline?: string }
}

function fmtAge(s: number | null | undefined) {
  if (s == null || Number.isNaN(s)) return null
  if (s < 60) return `${Math.round(s)}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  return `${Math.round(s / 3600)}h ago`
}

const PILLARS = [
  {
    title: 'Market research',
    body:
      'Event probabilities are a single number as of now. Short, medium, and long horizons are reserved for price paths, growth, and trends — each with data, evidence, and a falsifier.',
    href: '/research/',
    cta: 'Read research',
  },
  {
    title: 'Execution rails',
    body:
      'Autonomous trading only on designated agentic capital. Hard caps, wallet fences, and a kill switch. Client money never shares these rails.',
    href: '/trading/',
    cta: 'How execution works',
  },
  {
    title: 'Live operations',
    body:
      'Architecture telemetry, agent graph, and desk posture — so you can see the plant without guessing.',
    href: '/dashboard',
    cta: 'Open live desk',
  },
]

const METHOD = [
  {
    t: 'Observe',
    d: 'Public market data (crypto spot, dominance, macro proxies) plus portfolio multi-lens research on the book.',
  },
  {
    t: 'Estimate',
    d: 'One probability per binary event (e.g. “BTC cycle low is in”). Separate path bands for prices over short / medium / long.',
  },
  {
    t: 'Falsify',
    d: 'Every claim carries a written falsifier before the outcome. We score later — opinions without review are vibes.',
  },
  {
    t: 'Act (gated)',
    d: 'Trade ideas stay on designated wallets under caps. Speculation is allowed; silent overreach is not.',
  },
]

export default function MissionControl() {
  const [live, setLive] = useState<Live | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const pull = async () => {
      try {
        const res = await fetch('/api/v1/live', { cache: 'no-store' })
        if (!res.ok) throw new Error(`status ${res.status}`)
        const data = (await res.json()) as Live
        if (!cancelled) {
          setLive(data)
          setErr(null)
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : 'offline')
      }
    }
    pull()
    const id = window.setInterval(pull, 15_000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  const status = useMemo(() => {
    const st = live?.status
    const age = fmtAge(live?.freshness_s)
    const exec = live?.desk?.execution
    const agents = live?.agents?.length ?? 0
    const hasSignal = Boolean(st && st !== 'warming' && st !== 'offline')
    return { st, age, exec, agents, hasSignal, headline: live?.summary?.headline }
  }, [live])

  return (
    <div className="home-pro">
      {/* Hero — plain English, no empty gauges */}
      <section className="home-hero">
        <div className="home-hero-inner">
          <p className="home-kicker">Sapphire Alpha</p>
          <h1>
            Research-driven trading infrastructure
            <span className="home-h1-sub">you can actually inspect.</span>
          </h1>
          <p className="home-lede">
            We form data-backed market opinions, publish the reasoning with falsifiers, and
            run autonomous execution only on designated test and agentic capital — under caps
            and a kill switch.
          </p>
          <div className="home-cta">
            <Link href="/research/" className="btn-primary">
              Latest research
            </Link>
            <Link href="/dashboard" className="btn-secondary">
              Live desk
            </Link>
            <Link href="/trading/" className="btn-ghost">
              Execution design
            </Link>
          </div>

          {/* Status strip — only meaningful fields */}
          <div className="home-status" aria-label="System status">
            <div>
              <span>Telemetry</span>
              <strong>
                {err
                  ? 'Unavailable'
                  : status.st
                    ? status.st.charAt(0).toUpperCase() + status.st.slice(1)
                    : 'Connecting…'}
              </strong>
            </div>
            <div>
              <span>Last reading</span>
              <strong>{status.age ?? '—'}</strong>
            </div>
            <div>
              <span>Desk mode</span>
              <strong>{status.exec ? String(status.exec) : 'See live desk'}</strong>
            </div>
            <div>
              <span>Published research</span>
              <strong>
                <Link href="/research/conjecture-2026-07-27/">Event book · path bands</Link>
              </strong>
            </div>
          </div>
          {status.headline && status.hasSignal && (
            <p className="home-status-note">{status.headline}</p>
          )}
        </div>
      </section>

      {/* Three pillars */}
      <section className="home-section">
        <div className="home-section-inner">
          <p className="home-kicker">What this is</p>
          <h2>Three surfaces. One standard.</h2>
          <div className="home-pillars">
            {PILLARS.map((p) => (
              <article key={p.title} className="home-card">
                <h3>{p.title}</h3>
                <p>{p.body}</p>
                <Link href={p.href}>{p.cta} →</Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Methodology */}
      <section className="home-section home-section--raised">
        <div className="home-section-inner">
          <p className="home-kicker">How research works</p>
          <h2>Speculate with discipline.</h2>
          <p className="home-section-lede">
            The system is allowed to conjecture — including on ambiguous markets — but every
            claim is forced through data, a single event probability when the claim is binary,
            path horizons only for targets and trends, and a falsifier written in advance.
          </p>
          <ol className="home-method">
            {METHOD.map((m, i) => (
              <li key={m.t}>
                <span>{String(i + 1).padStart(2, '0')}</span>
                <div>
                  <strong>{m.t}</strong>
                  <p>{m.d}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="home-method-cta">
            <Link href="/research/conjecture-2026-07-27/" className="btn-primary">
              Read today’s opinions
            </Link>
            <Link href="/research/research-methodology/" className="btn-secondary">
              Research methodology
            </Link>
            <Link href="/research/how-research-is-published/" className="btn-ghost">
              Publication standard
            </Link>
          </div>
        </div>
      </section>

      {/* Honest scope */}
      <section className="home-section">
        <div className="home-section-inner home-scope">
          <div>
            <p className="home-kicker">Scope</p>
            <h2>What we will and will not claim.</h2>
          </div>
          <div className="home-scope-grid">
            <div>
              <h3>We publish</h3>
              <ul>
                <li>Event probabilities as of a timestamp</li>
                <li>Price path bands (short / medium / long)</li>
                <li>Evidence, sources, and falsifiers</li>
                <li>Architecture and execution design</li>
              </ul>
            </div>
            <div>
              <h3>We do not publish</h3>
              <ul>
                <li>Live account balances or holdings</li>
                <li>Wallet addresses in anonymous views</li>
                <li>Guaranteed returns or hit rates</li>
                <li>Advice for outside capital</li>
              </ul>
            </div>
          </div>
          <p className="home-disclaimer">
            Not investment advice. Opinions are for designated test and agentic capital only.
            Past calibration does not guarantee future accuracy.
          </p>
        </div>
      </section>
    </div>
  )
}

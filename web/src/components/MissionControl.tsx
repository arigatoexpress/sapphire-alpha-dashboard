'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  ConceptCards,
  MethodFlow,
  PathBandChart,
  ProbabilityRing,
} from '@/components/Visuals'

type Live = {
  status?: string
  freshness_s?: number | null
  desk?: {
    execution?: string | null
    posture?: string | null
  }
  summary?: { headline?: string }
}

function fmtAge(s: number | null | undefined) {
  if (s == null || Number.isNaN(s)) return null
  if (s < 60) return `${Math.round(s)}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  return `${Math.round(s / 3600)}h ago`
}

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
    return { st, age, exec, headline: live?.summary?.headline }
  }, [live])

  return (
    <div className="home-pro">
      {/* Hero */}
      <section className="home-hero">
        <div className="home-hero-mesh" aria-hidden="true" />
        <div className="home-hero-inner">
          <p className="home-kicker">Sapphire Alpha</p>
          <h1>
            Markets, researched.
            <span className="home-h1-sub">Trades, gated. Everything inspectable.</span>
          </h1>
          <p className="home-lede">
            We form clear market opinions from public data — one probability per event, path
            bands for price targets — then run autonomous execution only on designated capital
            under hard caps.
          </p>
          <div className="home-cta">
            <Link href="/research/" className="btn-primary">
              See today’s opinions
            </Link>
            <Link href="/dashboard" className="btn-secondary">
              Live desk
            </Link>
            <Link href="/research/research-methodology/" className="btn-ghost">
              How it works
            </Link>
          </div>

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
              <span>Rails</span>
              <strong>RH Agentic · MegaETH</strong>
            </div>
          </div>
        </div>
      </section>

      {/* Visual concept explainer */}
      <section className="home-section">
        <div className="home-section-inner">
          <p className="home-kicker">The idea in three pictures</p>
          <h2>Clear enough to disagree with.</h2>
          <p className="home-section-lede">
            No multi-horizon odds for the same event. No fake backtest leaderboards. Just a
            probability, a path, and a way to be wrong.
          </p>
          <ConceptCards />
        </div>
      </section>

      {/* Live sample viz from latest published book */}
      <section className="home-section home-section--raised">
        <div className="home-section-inner">
          <p className="home-kicker">From the latest book</p>
          <h2>What an opinion looks like.</h2>
          <div className="home-viz-row">
            <ProbabilityRing
              p={0.51}
              label="BTC cycle low is in"
              sub="Single event P · residual 49%"
            />
            <ProbabilityRing
              p={0.28}
              label="US recession ≤12m"
              sub="Lean no · confidence moderate"
            />
            <div className="home-viz-path-wrap">
              <PathBandChart
                asset="BTC"
                horizon="medium · 90d path"
                spot={65175}
                bear={46926}
                base={66500}
                bull={85000}
              />
              <p className="home-viz-caption">
                Path bands answer “where might price go?” — not “is the low in?” Those stay as
                one number above.
              </p>
            </div>
          </div>
          <div className="home-method-cta" style={{ marginTop: '1.75rem' }}>
            <Link href="/research/conjecture-2026-07-27/" className="btn-primary">
              Full opinion book
            </Link>
            <Link href="/research/research-methodology/" className="btn-secondary">
              Research methodology
            </Link>
          </div>
        </div>
      </section>

      {/* Method flow */}
      <section className="home-section">
        <div className="home-section-inner">
          <p className="home-kicker">How research works</p>
          <h2>Speculate with discipline.</h2>
          <p className="home-section-lede">
            The system is allowed to conjecture on ambiguous markets — including dubiously —
            but every claim is forced through data, a single event probability when binary, path
            horizons only for targets, and a falsifier written in advance.
          </p>
          <MethodFlow />
        </div>
      </section>

      {/* Rails */}
      <section className="home-section home-section--raised">
        <div className="home-section-inner">
          <p className="home-kicker">Execution</p>
          <h2>Two rails. Designated capital only.</h2>
          <div className="home-pillars">
            <article className="home-card home-card--glow">
              <p className="home-card-kicker">Rail 01</p>
              <h3>Robinhood Agentic</h3>
              <p>
                Free-reign equities, options, and crypto on the agentic account. Per-order and
                daily caps. Settlement cash is a real gate — no fantasy liquidity.
              </p>
              <Link href="/trading/">Strategy design →</Link>
            </article>
            <article className="home-card home-card--glow-ice">
              <p className="home-card-kicker">Rail 02</p>
              <h3>MegaETH · MOSS</h3>
              <p>
                Passkey session keys for USDm on MegaETH. Transfer-first lab scope, hard daily
                spend, no private keys in model context.
              </p>
              <Link href="/onchain/">On-chain design →</Link>
            </article>
            <article className="home-card">
              <p className="home-card-kicker">Always</p>
              <h3>Kill switch</h3>
              <p>
                Caps the strategy cannot argue with. A human can always pause. Client money never
                shares these rails.
              </p>
              <Link href="/dashboard">Open live desk →</Link>
            </article>
          </div>
        </div>
      </section>

      {/* Scope */}
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
                <li>Evidence, drivers, and falsifiers</li>
                <li>Architecture and execution design</li>
              </ul>
            </div>
            <div>
              <h3>We do not publish</h3>
              <ul>
                <li>Live balances or private holdings</li>
                <li>Paper backtest “strategy” leaderboards</li>
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

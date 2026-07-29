'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import type { LiveSnapshot } from '@shared/telemetry'
import SystemAtlas from '@/components/SystemAtlas'

type EvidenceState = 'observed' | 'stale' | 'paused' | 'unavailable' | 'source-only'

function fmtAge(seconds: number | null | undefined) {
  if (seconds == null || Number.isNaN(seconds)) return 'not observed'
  if (seconds < 60) return `${Math.round(seconds)}s ago`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`
  return `${Math.round(seconds / 3600)}h ago`
}

function fmtObservedAt(value: string | null | undefined) {
  if (!value) return 'not observed'
  const observed = new Date(value)
  if (Number.isNaN(observed.getTime())) return 'not observed'
  return observed.toISOString().replace('T', ' ').replace('.000Z', 'Z')
}

function words(value: string | null | undefined) {
  return value ? value.replace(/_/g, ' ') : 'not observed'
}

function evidenceState(value: string | null | undefined, opts?: { paused?: boolean }): EvidenceState {
  if (opts?.paused) return 'paused'
  const normalized = String(value ?? '').toLowerCase()
  if (!normalized || normalized === 'not observed' || normalized === 'unknown') return 'unavailable'
  if (normalized === 'stale' || normalized === 'delayed' || normalized === 'degraded') return 'stale'
  if (['halted', 'off', 'gated', 'disarmed', 'paused', 'read-only'].includes(normalized)) {
    return 'paused'
  }
  if (['live', 'current', 'healthy', 'verified', 'working', 'observed'].includes(normalized)) {
    return 'observed'
  }
  if (normalized === 'source-only' || normalized.includes('source')) return 'source-only'
  return 'unavailable'
}

const EVIDENCE_LEGEND: EvidenceState[] = [
  'observed',
  'stale',
  'paused',
  'unavailable',
  'source-only',
]

export default function MissionControl() {
  const [live, setLive] = useState<LiveSnapshot | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const pull = async () => {
      try {
        const response = await fetch('/api/v1/live', { cache: 'no-store' })
        if (!response.ok) throw new Error(`status ${response.status}`)
        const data = (await response.json()) as LiveSnapshot
        if (!cancelled) {
          setLive(data)
          setError('')
        }
      } catch (reason) {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : 'unavailable')
        }
      }
    }
    pull()
    const timer = window.setInterval(pull, 15_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  const state = useMemo(() => {
    const runtimeCurrent = live?.status === 'live'
    const execution = runtimeCurrent
      ? live?.desk?.execution ?? live?.markets?.execution ?? null
      : null
    const retained = Boolean(error && live)
    const statusLabel = error ? 'unavailable' : (live?.status ?? 'not observed')
    const execWords = runtimeCurrent ? words(execution) : 'unknown'
    const paused =
      ['halted', 'off', 'gated', 'paused'].includes(String(execution).toLowerCase())

    return {
      status: statusLabel,
      statusState: error
        ? ('unavailable' as EvidenceState)
        : evidenceState(live?.status),
      observedAt: fmtObservedAt(live?.observed_at),
      observedState: live?.observed_at
        ? error
          ? ('stale' as EvidenceState)
          : ('observed' as EvidenceState)
        : ('unavailable' as EvidenceState),
      freshness: error
        ? retained
          ? `poll failed · last report ${fmtAge(live?.freshness_s)}`
          : 'poll failed'
        : fmtAge(live?.freshness_s),
      freshnessState: error
        ? retained
          ? ('stale' as EvidenceState)
          : ('unavailable' as EvidenceState)
        : live?.freshness_s != null
          ? live.status === 'stale'
            ? ('stale' as EvidenceState)
            : ('observed' as EvidenceState)
          : ('unavailable' as EvidenceState),
      execution: execWords,
      executionState: error
        ? retained
          ? ('stale' as EvidenceState)
          : ('unavailable' as EvidenceState)
        : evidenceState(execWords, { paused }),
      market: runtimeCurrent
        ? words(live?.markets?.status)
        : live?.status === 'stale'
          ? 'stale'
          : 'unknown',
      marketState: error
        ? ('unavailable' as EvidenceState)
        : evidenceState(
            runtimeCurrent ? live?.markets?.status : live?.status === 'stale' ? 'stale' : null,
          ),
      gate: runtimeCurrent ? words(live?.markets?.decision_gate) : 'unknown',
      gateState: runtimeCurrent
        ? evidenceState(live?.markets?.decision_gate)
        : ('unavailable' as EvidenceState),
    }
  }, [live, error])

  const horizon = [
    { label: 'Snapshot', value: state.status, state: state.statusState, source: '/api/v1/live' },
    {
      label: 'Source time',
      value: state.observedAt,
      state: state.observedState,
      source: 'observed_at',
    },
    {
      label: 'Age',
      value: state.freshness,
      state: state.freshnessState,
      source: 'freshness_s',
    },
    {
      label: 'Market feed',
      value: state.market,
      state: state.marketState,
      source: 'markets.status',
    },
    {
      label: 'Execution',
      value: state.execution,
      state: state.executionState,
      source: 'desk.execution',
    },
  ]

  return (
    <div className="public-observatory">
      <section className="public-hero" aria-labelledby="public-title">
        <div>
          <p className="public-kicker">Sapphire · Research OS</p>
          <h1 id="public-title">A system that shows its work.</h1>
          <p className="public-lede">
            Sapphire is a self-sovereign research and trading operating system. The public
            record explains what it observes, how it reasons, what it has actually produced,
            and what is currently paused or unavailable — without presenting absence as
            health.
          </p>
          <div className="public-actions">
            <Link href="/research/" className="public-action public-action--primary">
              Read research
            </Link>
            <Link href="/architecture/" className="public-action">
              System map
            </Link>
          </div>
        </div>

        <div
          className="public-hero-horizon horizon-enter"
          aria-label="Evidence horizon"
          data-signature="evidence-horizon"
        >
          <div className="public-horizon-title">
            <span>Evidence horizon</span>
            <b>Admitted truth only</b>
          </div>
          <p className="public-horizon-legend" aria-label="Evidence states">
            {EVIDENCE_LEGEND.map((s) => (
              <span key={s} data-evidence-state={s}>
                {s}
              </span>
            ))}
          </p>
          {horizon.map((item) => (
            <div
              className="public-horizon-row"
              data-evidence-state={item.state}
              data-tone={item.state}
              key={item.label}
            >
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
          <p>
            Source: <code>/api/v1/live</code> · authority: none · unknown stays unknown ·
            response generation is not the observation time.
          </p>
        </div>
      </section>

      <SystemAtlas snapshot={live} sourceError={error} />

      <section className="public-thesis" aria-labelledby="does-title">
        <div>
          <p className="public-kicker">What the system does</p>
          <h2 id="does-title">Observe. Reason. Gate. Score.</h2>
        </div>
        <div className="public-thesis-copy">
          <p>
            Claims become evidence through a fixed path: cite the source and retrieval time,
            form one event probability, write the falsifier before the outcome, hold
            execution behind policy, then resolve and publish the error.
          </p>
          <Link href="/research/research-methodology/">How claims become evidence →</Link>
        </div>
      </section>

      <section className="public-method" aria-labelledby="method-title">
        <div>
          <p className="public-kicker">How claims become evidence</p>
          <h2 id="method-title">The record is the product.</h2>
        </div>
        <ol>
          {[
            ['01', 'Observe', 'Cite the source and the moment it was retrieved.'],
            ['02', 'Form', 'One event probability; path bands stay separate.'],
            ['03', 'Falsify', 'Write the failure condition before the outcome.'],
            ['04', 'Gate', 'Evidence may propose. Policy and people hold authority.'],
            ['05', 'Score', 'Resolve the event, publish the error, update the prior.'],
          ].map(([index, title, body]) => (
            <li key={index}>
              <span>{index}</span>
              <strong>{title}</strong>
              <p>{body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="public-entry public-ledger-grid" aria-labelledby="ledger-title">
        <div>
          <p className="public-kicker">Latest work</p>
          <h2 id="ledger-title">Research ledger</h2>
          <div className="public-entry-links">
            <Link href="/research/conjecture-2026-07-27/">
              <span>Opinion book</span>
              <b>Evidence, probability, path, falsifier →</b>
            </Link>
            <Link href="/research/calibration-2026-07-27/">
              <span>Calibration</span>
              <b>Scored outcomes and residual error →</b>
            </Link>
            <Link href="/research/">
              <span>Full index</span>
              <b>All published reports →</b>
            </Link>
          </div>
        </div>
        <div>
          <p className="public-kicker">Boundaries</p>
          <h2 id="principles-title">Operating principles</h2>
          <dl className="public-principles">
            <div>
              <dt>Truth</dt>
              <dd>A number is observed, or it is absent — never zero-filled.</dd>
            </div>
            <div>
              <dt>Pause</dt>
              <dd>Paused or stale capability is not presented as live.</dd>
            </div>
            <div>
              <dt>Authority</dt>
              <dd>This surface cannot trade, approve, or clear a kill switch.</dd>
            </div>
            <div>
              <dt>Privacy</dt>
              <dd>No wallet identifiers, exact balances, or personal attribution.</dd>
            </div>
          </dl>
          <p className="public-disclaimer">
            Not investment advice. No guaranteed returns, private positions, or paper
            backtest leaderboards are published here.
          </p>
        </div>
      </section>
    </div>
  )
}

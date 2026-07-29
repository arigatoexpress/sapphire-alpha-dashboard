'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import ArchitectureMesh from './ArchitectureMesh'

type Live = {
  status?: string
  observed_at?: string | null
  freshness_s?: number | null
  desk?: {
    execution?: string | null
    posture?: string | null
    decisions?: {
      pending_review?: number | null
      blocked?: number | null
    }
  }
  markets?: {
    status?: string | null
    decision_gate?: string | null
    execution?: string | null
  }
}

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

function stateTone(value: string | null | undefined) {
  const normalized = String(value ?? '').toLowerCase()
  if (['live', 'current', 'verified'].includes(normalized)) return 'current'
  if (['halted', 'off', 'gated', 'manual', 'telegram'].includes(normalized)) return 'held'
  if (['stale', 'delayed', 'degraded', 'offline', 'failed'].includes(normalized)) {
    return 'degraded'
  }
  return 'unknown'
}

export default function MissionControl() {
  const [live, setLive] = useState<Live | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const pull = async () => {
      try {
        const response = await fetch('/api/v1/live', { cache: 'no-store' })
        if (!response.ok) throw new Error(`status ${response.status}`)
        const data = (await response.json()) as Live
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
    const execution = live?.desk?.execution ?? live?.markets?.execution ?? null
    const retained = Boolean(error && live)
    return {
      status: error ? 'unavailable' : (live?.status ?? 'not observed'),
      observedAt: fmtObservedAt(live?.observed_at),
      freshness: error ? (retained ? `poll failed · last report ${fmtAge(live?.freshness_s)}` : 'poll failed') : fmtAge(live?.freshness_s),
      execution: words(execution),
      executionTone: error ? (retained ? 'degraded' : 'unknown') : stateTone(execution),
      market: words(live?.markets?.status),
      gate: words(live?.markets?.decision_gate),
      sourceTone: (value: string | null | undefined) =>
        error ? (retained && value ? 'degraded' : 'unknown') : stateTone(value),
    }
  }, [live, error])

  return (
    <div className="public-observatory">
      <section className="public-hero" aria-labelledby="public-title">
        <div>
          <p className="public-kicker">Sapphire Alpha · decision observatory</p>
          <h1 id="public-title">
            Evidence
            <span>before action.</span>
          </h1>
          <p className="public-lede">
            A market claim should show its source, its age, the authority it carries,
            and what would prove it wrong. Sapphire makes that contract visible before
            any designated execution rail can act.
          </p>
          <div className="public-actions">
            <Link href="/research/" className="public-action public-action--primary">
              Read the evidence
            </Link>
            <Link href="/dashboard" className="public-action">
              Open the observatory
            </Link>
          </div>
        </div>

        <div className="public-hero-horizon" aria-label="Current evidence horizon">
          <div className="public-horizon-title">
            <span>Evidence horizon</span>
            <b>Read only</b>
          </div>
          {[
            { label: 'Snapshot', value: state.status, tone: stateTone(state.status) },
            { label: 'Last report', value: state.observedAt, tone: state.sourceTone(live?.observed_at) },
            { label: 'Freshness', value: state.freshness, tone: state.sourceTone(live?.status) },
            { label: 'Market feed', value: state.market, tone: state.sourceTone(live?.markets?.status) },
            { label: 'Execution', value: state.execution, tone: state.executionTone },
          ].map((item) => (
            <div className="public-horizon-row" data-tone={item.tone} key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
          <p>
            Source: <code>/api/v1/live</code> · authority: none · unknown stays unknown.
          </p>
        </div>
      </section>

      <section className="public-thesis" aria-labelledby="thesis-title">
        <div>
          <p className="public-kicker">The thesis</p>
          <h2 id="thesis-title">Clear enough to disagree with.</h2>
        </div>
        <div className="public-thesis-copy">
          <p>
            Sapphire separates the binary claim from the price path. An event gets one
            probability at one timestamp. Bear, base, and bull belong to the path—not as
            three incompatible probabilities for the same event.
          </p>
          <Link href="/research/research-methodology/">Inspect the method →</Link>
        </div>
      </section>

      <section className="public-method" aria-labelledby="method-title">
        <div>
          <p className="public-kicker">How a claim travels</p>
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

      <section className="public-mesh" aria-labelledby="mesh-title">
        <div className="public-mesh-preface">
          <p className="public-kicker">The system, in one view</p>
          <h2 id="mesh-title">
            Five verbs, on hardware you can point at.
          </h2>
          <p>
            The method above is not an idea. It runs on four small computers on
            a private network, holds five paper-trading strategies, and passes
            every proposal through a gate that a human still owns.
          </p>
          <Link href="/architecture/" className="public-mesh-link">
            Inspect the machine →
          </Link>
        </div>
        <ArchitectureMesh variant="compact" />
      </section>

      <section className="public-state" aria-labelledby="state-title">
        <div className="public-state-copy">
          <p className="public-kicker">Current boundary</p>
          <h2 id="state-title">
            Authority held.
            <span>No execution is available from this page.</span>
          </h2>
          <p>
            The public observatory is anonymous and read only. It cannot place a trade,
            approve a proposal, clear a kill switch, increase a cap, or reveal a private
            holding.
          </p>
        </div>
        <dl>
          <div>
            <dt>Execution</dt>
            <dd data-tone={state.executionTone}>{state.execution}</dd>
          </div>
          <div>
            <dt>Decision gate</dt>
            <dd>{state.gate}</dd>
          </div>
          <div>
            <dt>Capital</dt>
            <dd>Designated rails only</dd>
          </div>
          <div>
            <dt>Public authority</dt>
            <dd>None</dd>
          </div>
        </dl>
      </section>

      <section className="public-entry" aria-labelledby="entry-title">
        <div>
          <p className="public-kicker">Enter the record</p>
          <h2 id="entry-title">Read the latest claim, then inspect the system that holds it.</h2>
        </div>
        <div className="public-entry-links">
          <Link href="/research/conjecture-2026-07-27/">
            <span>Latest opinion book</span>
            <b>Evidence, probability, path, falsifier →</b>
          </Link>
          <Link href="/proof/">
            <span>Authority contract</span>
            <b>Proposal, mandate, intent, execution →</b>
          </Link>
          <Link href="/dashboard">
            <span>Live observatory</span>
            <b>What changed, needs attention, can act →</b>
          </Link>
        </div>
        <p className="public-disclaimer">
          Not investment advice. No guaranteed returns, private positions, or paper
          backtest leaderboards are published here.
        </p>
      </section>
    </div>
  )
}

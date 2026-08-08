'use client'

import { useEffect, useMemo, useState } from 'react'
import type { LiveSnapshot } from '@shared/telemetry'
import { startLivePoller } from '@/components/live-poller'

function observedTime(value: string | null | undefined) {
  if (!value) return 'not observed'
  const instant = new Date(value)
  if (Number.isNaN(instant.getTime())) return 'not observed'
  return instant.toISOString().replace('.000Z', 'Z')
}

function age(seconds: number | null | undefined) {
  if (seconds == null || !Number.isFinite(seconds)) return 'not observed'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

export default function LiveTruthRail() {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null)
  const [error, setError] = useState('')

  useEffect(
    () =>
      startLivePoller({
        fetcher: window.fetch.bind(window),
        onSnapshot: (next) => {
          setSnapshot(next)
          setError('')
        },
        onUnavailable: setError,
      }),
    [],
  )

  const rail = useMemo(() => {
    const current = snapshot?.status === 'live' && !error
    const execution = current
      ? snapshot?.desk?.execution ?? snapshot?.markets?.execution ?? 'unknown'
      : 'unknown'
    return [
      {
        label: 'Observation',
        value: current ? observedTime(snapshot?.observed_at) : 'not observed',
        meta: current ? `age ${age(snapshot?.freshness_s)}` : 'waiting for admitted telemetry',
        state: current ? 'observed' : error ? 'unavailable' : 'source-only',
      },
      {
        label: 'Claim',
        value: current ? 'Runtime report admitted' : 'No current runtime claim',
        meta: 'source /api/v1/live',
        state: current ? 'observed' : 'source-only',
      },
      {
        label: 'Falsifier',
        value: 'Poll failure or expired source time',
        meta: 'response time never replaces observation time',
        state: 'source-only',
      },
      {
        label: 'Confidence',
        value: current ? 'Contract-shaped observation' : 'Unscored',
        meta: 'shape validation is not analytical confidence',
        state: current ? 'observed' : 'source-only',
      },
      {
        label: 'Authority',
        value: 'None',
        meta: `execution ${String(execution).replaceAll('_', ' ')}`,
        state: 'paused',
      },
    ]
  }, [snapshot, error])

  const announcement = error
    ? 'Live telemetry unavailable'
    : snapshot?.status === 'live'
      ? 'Live telemetry admitted'
      : snapshot?.status === 'stale'
        ? 'Live telemetry stale'
        : 'Waiting for live telemetry'

  return (
    <aside
      className="truth-rail"
      data-signature="truth-rail"
      aria-label="Truth rail"
    >
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>
      <header>
        <span>Truth rail</span>
        <strong>Live evidence contract</strong>
      </header>
      <ol>
        {rail.map((item, index) => (
          <li key={item.label} data-evidence-state={item.state}>
            <span className="truth-rail__index">0{index + 1}</span>
            <div>
              <p>{item.label}</p>
              <strong>{item.value}</strong>
              <small>{item.meta}</small>
            </div>
          </li>
        ))}
      </ol>
    </aside>
  )
}

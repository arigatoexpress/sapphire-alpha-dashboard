'use client'

import { useEffect, useState } from 'react'

/**
 * Shape of the anonymous /api/v1/live response, narrowed to just the fields the
 * marketing site reads. The API can add fields; anything unknown is ignored.
 * Every value here is optional because the backend explicitly renders `null`
 * for anything a producer has not observed — never a made-up zero.
 */
export type Live = {
  observed_at?: string | null
  served_at?: string | null
  freshness_s?: number | null
  status?: string | null
  version?: number | null
  sequence?: number | null

  summary?: {
    state?: string | null
    attention?: number | null
    active_agents?: number | null
    verified_today?: number | null
    events_per_min?: number | null
  } | null

  agents?: Array<{
    id: string
    role: string
    provider_class?: string | null
    state?: string | null
    verification?: string | null
    activity?: string | null
    updated_at?: string | null
  }> | null

  markets?: {
    status?: string | null
    execution?: string | null
    decision_gate?: string | null
    network?: string | null
    feed_age_s?: number | null
    events_per_min?: number | null
    paper_strategies?: number | null
  } | null

  desk?: {
    posture?: string | null
    execution?: string | null
    leader?: string | null
    updated_at?: string | null
    decisions?: {
      pending?: number | null
      pending_review?: number | null
      blocked?: number | null
      pending_policy_blocked?: number | null
      approved_awaiting_execution?: number | null
      eligible_execution?: number | null
    } | null
    feeds?: { fresh?: number | null; total?: number | null } | null
    tracks?: Array<{
      strategy: string
      status?: string | null
      live_return_pct?: number | null
      open_count?: number | null
      green_days?: number | null
      target_days?: number | null
      freshness_s?: number | null
      data_flags?: number | null
    }> | null
    validation?: {
      oos_pass?: number | null
      oos_total?: number | null
      conflicts?: number | null
      replay_span_hours?: number | null
    } | null
  } | null

  nodes?: Array<{
    id: string
    zone?: string | null
    health?: string | null
    load?: string | null
    freshness_s?: number | null
  }> | null

  links?: Array<{
    source: string
    target: string
    class?: string | null
    events_per_min?: number | null
  }> | null

  events?: Array<{
    id: string
    class?: string | null
    state?: string | null
    updated_at?: string | null
    detail?: string | null
  }> | null
}

export type LiveState =
  | { status: 'loading'; data: null; error: null; fetchedAt: null }
  | { status: 'ok'; data: Live; error: null; fetchedAt: number }
  | { status: 'stale'; data: Live; error: string; fetchedAt: number }
  | { status: 'error'; data: null; error: string; fetchedAt: null }

const INITIAL: LiveState = { status: 'loading', data: null, error: null, fetchedAt: null }

/*
 * Module-level singleton: exactly one polling loop per page load, no matter how
 * many components subscribe. React StrictMode double-invokes effects in dev, and
 * the mesh + intelligence sections both need this data — without a singleton we
 * would double or triple the request rate on every mount.
 */
let current: LiveState = INITIAL
const subscribers = new Set<(state: LiveState) => void>()
let poller: ReturnType<typeof setInterval> | null = null
let inFlight: AbortController | null = null

const POLL_MS = 15_000

function publish(next: LiveState) {
  current = next
  for (const notify of subscribers) notify(next)
}

async function pull() {
  inFlight?.abort()
  const controller = new AbortController()
  inFlight = controller
  try {
    const response = await fetch('/api/v1/live', {
      cache: 'no-store',
      signal: controller.signal,
    })
    if (!response.ok) throw new Error(`http ${response.status}`)
    const data = (await response.json()) as Live
    publish({ status: 'ok', data, error: null, fetchedAt: Date.now() })
  } catch (reason) {
    if (controller.signal.aborted) return
    const message = reason instanceof Error ? reason.message : 'unavailable'
    if (current.status === 'ok' || current.status === 'stale') {
      publish({ status: 'stale', data: current.data, error: message, fetchedAt: current.fetchedAt })
    } else {
      publish({ status: 'error', data: null, error: message, fetchedAt: null })
    }
  } finally {
    if (inFlight === controller) inFlight = null
  }
}

function start() {
  if (poller != null) return
  pull()
  poller = setInterval(pull, POLL_MS)
}

function stop() {
  if (poller != null) {
    clearInterval(poller)
    poller = null
  }
  inFlight?.abort()
  inFlight = null
}

export function useLiveTelemetry(): LiveState {
  const [state, setState] = useState<LiveState>(current)

  useEffect(() => {
    subscribers.add(setState)
    if (subscribers.size === 1) start()
    setState(current)
    return () => {
      subscribers.delete(setState)
      if (subscribers.size === 0) stop()
    }
  }, [])

  return state
}

/** Human age like "3s ago", "2m ago", "4h ago", or "not observed". */
export function formatAge(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return 'not observed'
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}

export function formatObservedAt(value: string | null | undefined): string {
  if (!value) return 'not observed'
  const observed = new Date(value)
  if (Number.isNaN(observed.getTime())) return 'not observed'
  return observed.toISOString().replace('T', ' ').replace('.000Z', 'Z').replace(/\.\d+Z$/, 'Z')
}

export function humanize(value: string | null | undefined, fallback = 'not observed'): string {
  return value ? value.replace(/_/g, ' ') : fallback
}

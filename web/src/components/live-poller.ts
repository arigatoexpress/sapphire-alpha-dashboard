import type { LiveSnapshot } from '@shared/telemetry'

export const LIVE_POLL_INTERVAL_MS = 15_000
export const LIVE_POLL_TIMEOUT_MS = 10_000
export const LIVE_SERVER_STALE_AFTER_MS = 180_000
export const LIVE_CLIENT_MAX_AGE_MS = LIVE_POLL_INTERVAL_MS * 2

type Fetcher = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>

type LivePollerOptions = {
  fetcher: Fetcher
  onSnapshot: (snapshot: LiveSnapshot) => void
  onUnavailable: (reason: string) => void
}

function reasonMessage(reason: unknown) {
  if (reason instanceof Error && reason.message) return reason.message
  return 'unavailable'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isIsoInstant(value: unknown) {
  return (
    typeof value === 'string' &&
    value.length > 0 &&
    /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) &&
    Number.isFinite(Date.parse(value))
  )
}

function isEnumString(value: unknown, members: readonly string[]) {
  return typeof value === 'string' && members.includes(value)
}

/**
 * Runtime admission boundary for the public poller. This deliberately checks
 * the complete top-level serving contract plus the nested fields consumed by
 * public components; TypeScript casts alone are never evidence.
 */
export function isLiveSnapshot(value: unknown): value is LiveSnapshot {
  if (!isRecord(value)) return false
  if (value.version !== 1) return false
  if (!isEnumString(value.status, ['live', 'stale', 'warming', 'offline'])) return false
  if (!isIsoInstant(value.served_at)) return false
  if (!isRecord(value.summary) || !isRecord(value.markets) || !isRecord(value.desk)) {
    return false
  }
  if (!Array.isArray(value.nodes) || !Array.isArray(value.links)) return false
  if (!Array.isArray(value.agents) || !Array.isArray(value.events)) return false

  if (value.status === 'live' || value.status === 'stale') {
    if (!isIsoInstant(value.observed_at)) return false
    if (
      typeof value.freshness_s !== 'number' ||
      !Number.isFinite(value.freshness_s) ||
      value.freshness_s < 0
    ) return false
    if (
      typeof value.sequence !== 'number' ||
      !Number.isFinite(value.sequence) ||
      !Number.isInteger(value.sequence) ||
      value.sequence < 0
    ) return false
  } else if (
    value.observed_at !== null ||
    value.freshness_s !== null ||
    value.sequence !== null ||
    value.nodes.length !== 0 ||
    value.links.length !== 0 ||
    value.agents.length !== 0 ||
    value.events.length !== 0
  ) {
    return false
  }

  if (
    !isEnumString(value.markets.status, ['current', 'delayed', 'stale', 'offline']) ||
    !isEnumString(value.markets.decision_gate, ['manual', 'off', 'unknown']) ||
    !isEnumString(value.markets.execution, ['off', 'paper', 'gated', 'halted', 'unknown'])
  ) return false
  if (
    'execution' in value.desk &&
    !isEnumString(value.desk.execution, ['halted', 'off', 'gated', 'unknown'])
  ) return false
  return true
}

function clientExpiryMs(snapshot: LiveSnapshot) {
  if (
    snapshot.status !== 'live' ||
    snapshot.freshness_s == null ||
    !Number.isFinite(snapshot.freshness_s)
  ) {
    return null
  }
  const serverRemaining =
    LIVE_SERVER_STALE_AFTER_MS - Math.max(0, snapshot.freshness_s) * 1_000
  return Math.max(0, Math.min(LIVE_CLIENT_MAX_AGE_MS, serverRemaining))
}

export function startLivePoller({
  fetcher,
  onSnapshot,
  onUnavailable,
}: LivePollerOptions) {
  let stopped = false
  let generation = 0
  let activeController: AbortController | null = null
  let nextTimer: ReturnType<typeof setTimeout> | null = null
  let expiryTimer: ReturnType<typeof setTimeout> | null = null

  const clearExpiry = () => {
    if (expiryTimer != null) clearTimeout(expiryTimer)
    expiryTimer = null
  }

  const armExpiry = (snapshot: LiveSnapshot, requestGeneration: number) => {
    clearExpiry()
    const delay = clientExpiryMs(snapshot)
    if (delay == null) return
    const expire = () => {
      if (!stopped && requestGeneration === generation) {
        onUnavailable('client evidence expired')
      }
    }
    if (delay === 0) {
      expire()
      return
    }
    expiryTimer = setTimeout(expire, delay)
  }

  const scheduleNext = (pull: () => Promise<void>) => {
    if (!stopped) nextTimer = setTimeout(pull, LIVE_POLL_INTERVAL_MS)
  }

  const pull = async () => {
    if (stopped) return
    const requestGeneration = ++generation
    const controller = new AbortController()
    activeController = controller
    let timeoutTimer: ReturnType<typeof setTimeout> | null = null

    const timeout = new Promise<never>((_resolve, reject) => {
      timeoutTimer = setTimeout(() => {
        controller.abort()
        reject(new Error('poll timeout'))
      }, LIVE_POLL_TIMEOUT_MS)
    })

    try {
      const request = async () => {
        const response = await fetcher('/api/v1/live', {
          cache: 'no-store',
          signal: controller.signal,
        })
        if (!response.ok) throw new Error(`status ${response.status}`)
        const payload: unknown = await response.json()
        if (!isLiveSnapshot(payload)) throw new Error('invalid live snapshot')
        return payload
      }
      const snapshot = await Promise.race([request(), timeout])
      if (stopped || requestGeneration !== generation) return
      onSnapshot(snapshot)
      armExpiry(snapshot, requestGeneration)
    } catch (reason) {
      if (!stopped && requestGeneration === generation) {
        onUnavailable(reasonMessage(reason))
      }
    } finally {
      if (timeoutTimer != null) clearTimeout(timeoutTimer)
      if (activeController === controller) activeController = null
      if (!stopped && requestGeneration === generation) scheduleNext(pull)
    }
  }

  void pull()

  return () => {
    stopped = true
    generation += 1
    activeController?.abort()
    if (nextTimer != null) clearTimeout(nextTimer)
    clearExpiry()
  }
}

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
        return (await response.json()) as LiveSnapshot
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

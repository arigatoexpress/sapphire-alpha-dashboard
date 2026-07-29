import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { LiveSnapshot } from '@shared/telemetry'
import liveFixture from '../../../shared/__tests__/fixtures/live-snapshot.json'
import {
  LIVE_POLL_INTERVAL_MS,
  LIVE_POLL_TIMEOUT_MS,
  startLivePoller,
} from './live-poller'

const fresh = liveFixture as LiveSnapshot

function response(snapshot: LiveSnapshot) {
  return {
    ok: true,
    status: 200,
    json: async () => snapshot,
  } as Response
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((accept) => {
    resolve = accept
  })
  return { promise, resolve }
}

describe('public live telemetry poller', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('fails closed on a hung request before another poll can overlap', async () => {
    const fetcher = vi.fn(() => new Promise<Response>(() => undefined))
    const onSnapshot = vi.fn()
    const onUnavailable = vi.fn()
    const stop = startLivePoller({ fetcher, onSnapshot, onUnavailable })

    expect(fetcher).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(LIVE_POLL_TIMEOUT_MS - 1)
    expect(onUnavailable).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(onUnavailable).toHaveBeenCalledWith('poll timeout')
    expect(onSnapshot).not.toHaveBeenCalled()
    expect(fetcher).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(LIVE_POLL_INTERVAL_MS)
    expect(fetcher).toHaveBeenCalledTimes(2)
    stop()
  })

  it('applies the same timeout while a response body is hanging', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => new Promise<LiveSnapshot>(() => undefined),
    } as Response)
    const onSnapshot = vi.fn()
    const onUnavailable = vi.fn()
    const stop = startLivePoller({ fetcher, onSnapshot, onUnavailable })

    await vi.advanceTimersByTimeAsync(LIVE_POLL_TIMEOUT_MS)
    expect(onUnavailable).toHaveBeenCalledWith('poll timeout')
    expect(onSnapshot).not.toHaveBeenCalled()
    stop()
  })

  it('recovers after a rejected poll and clears the failure through fresh evidence', async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue(response(fresh))
    const onSnapshot = vi.fn()
    const onUnavailable = vi.fn()
    const stop = startLivePoller({ fetcher, onSnapshot, onUnavailable })

    await vi.advanceTimersByTimeAsync(0)
    expect(onUnavailable).toHaveBeenCalledWith('offline')
    expect(onSnapshot).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(LIVE_POLL_INTERVAL_MS)
    expect(onSnapshot).toHaveBeenCalledWith(fresh)
    stop()
  })

  it('ignores a late response after timeout instead of overwriting newer evidence', async () => {
    const first = deferred<Response>()
    const next = structuredClone(fresh)
    next.sequence = (fresh.sequence ?? 0) + 1
    const fetcher = vi
      .fn()
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce(response(next))
    const onSnapshot = vi.fn()
    const onUnavailable = vi.fn()
    const stop = startLivePoller({ fetcher, onSnapshot, onUnavailable })

    await vi.advanceTimersByTimeAsync(
      LIVE_POLL_TIMEOUT_MS + LIVE_POLL_INTERVAL_MS,
    )
    expect(onSnapshot).toHaveBeenCalledTimes(1)
    expect(onSnapshot).toHaveBeenLastCalledWith(next)

    first.resolve(response(fresh))
    await vi.advanceTimersByTimeAsync(0)
    expect(onSnapshot).toHaveBeenCalledTimes(1)
    stop()
  })

  it('expires near-stale evidence from monotonic client time', async () => {
    const nearStale = structuredClone(fresh)
    nearStale.freshness_s = 175
    const fetcher = vi.fn().mockResolvedValue(response(nearStale))
    const onSnapshot = vi.fn()
    const onUnavailable = vi.fn()
    const stop = startLivePoller({ fetcher, onSnapshot, onUnavailable })

    await vi.advanceTimersByTimeAsync(0)
    expect(onSnapshot).toHaveBeenCalledWith(nearStale)

    await vi.advanceTimersByTimeAsync(4_999)
    expect(onUnavailable).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(onUnavailable).toHaveBeenCalledWith('client evidence expired')
    stop()
  })
})

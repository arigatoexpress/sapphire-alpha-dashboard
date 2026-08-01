import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const setSnapshot = vi.fn()
const setError = vi.fn()
const setLoading = vi.fn()
const addEventListener = vi.fn()
const removeEventListener = vi.fn()
let effectCleanup: void | (() => void)

vi.mock('react', () => ({
  useCallback: (callback: () => Promise<void>) => callback,
  useEffect: (effect: () => void | (() => void)) => {
    effectCleanup = effect()
  },
  useState: (initial: unknown) => {
    if (initial === null) return [initial, setSnapshot]
    if (initial === '') return [initial, setError]
    return [initial, setLoading]
  },
}))

import { useLiveTelemetry } from '../hooks/useLiveTelemetry'

describe('useLiveTelemetry', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    effectCleanup = undefined
    vi.stubGlobal('window', {
      setInterval: vi.fn()
        .mockReturnValueOnce(1)
        .mockReturnValueOnce(2),
      clearInterval: vi.fn(),
    })
    vi.stubGlobal('document', {
      visibilityState: 'visible',
      addEventListener,
      removeEventListener,
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('bypasses the browser cache for every live snapshot request', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ version: 1 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    useLiveTelemetry()

    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/v1/live', { cache: 'no-store' })
    })
  })

  it('polls at the admitted cadence and pauses hidden tabs', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ version: 1 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    useLiveTelemetry()

    await vi.waitFor(() => {
      expect(window.setInterval).toHaveBeenCalledWith(expect.any(Function), 15_000)
      expect(addEventListener).toHaveBeenCalledWith(
        'visibilitychange',
        expect.any(Function),
      )
    })

    const visibilityHandler = addEventListener.mock.calls.find(
      ([event]) => event === 'visibilitychange',
    )?.[1] as (() => void) | undefined
    expect(visibilityHandler).toBeTypeOf('function')

    ;(document as { visibilityState: string }).visibilityState = 'hidden'
    visibilityHandler?.()
    expect(window.clearInterval).toHaveBeenCalledWith(1)
    expect(window.setInterval).toHaveBeenCalledTimes(1)

    ;(document as { visibilityState: string }).visibilityState = 'visible'
    visibilityHandler?.()
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(window.setInterval).toHaveBeenCalledTimes(2)

    effectCleanup?.()
    expect(window.clearInterval).toHaveBeenNthCalledWith(1, 1)
    expect(window.clearInterval).toHaveBeenNthCalledWith(2, 2)
    expect(removeEventListener).toHaveBeenCalledWith(
      'visibilitychange',
      visibilityHandler,
    )
  })

  it('does not spend the shared read budget while initially hidden', async () => {
    vi.stubGlobal('document', {
      visibilityState: 'hidden',
      addEventListener,
      removeEventListener,
    })
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    useLiveTelemetry()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(window.setInterval).not.toHaveBeenCalled()
  })
})

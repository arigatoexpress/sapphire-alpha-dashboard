import { describe, expect, it } from 'vitest'
import {
  executionTone,
  flowProfile,
  formatAge,
  formatCount,
  formatExecution,
  formatExecutionHeadline,
  formatLatency,
  formatNewRisk,
  formatPercent,
  formatPosture,
  formatRate,
  formatSignedPercent,
  formatSignedPoints,
  NOT_MEASURED,
  NOT_OBSERVED,
  riskTone,
} from '../desk/format'
import { liveSnapshot } from './fixture'

describe('formatLatency', () => {
  it('says so when nothing measured the hop', () => {
    expect(formatLatency(null)).toBe(NOT_MEASURED)
    expect(formatLatency(undefined)).toBe(NOT_MEASURED)
    expect(formatLatency(Number.NaN)).toBe(NOT_MEASURED)
  })

  it('never turns an absent reading into a number', () => {
    for (const absent of [null, undefined, Number.NaN]) {
      expect(formatLatency(absent)).not.toMatch(/\d/)
    }
  })

  it('renders a real reading, including a real zero', () => {
    expect(formatLatency(0)).toBe('0 ms')
    expect(formatLatency(4.26)).toBe('4.3 ms')
    expect(formatLatency(34.2)).toBe('34 ms')
    expect(formatLatency(512)).toBe('512 ms')
  })

  it('is the only thing that distinguishes a measured zero from no measurement', () => {
    expect(formatLatency(0)).not.toBe(formatLatency(null))
  })
})

describe('formatRate', () => {
  it('reports absence as absence and zero as zero', () => {
    expect(formatRate(null)).toBe(NOT_MEASURED)
    expect(formatRate(undefined)).toBe(NOT_MEASURED)
    expect(formatRate(0)).toBe('0/min')
  })

  it('renders measured rates', () => {
    expect(formatRate(24)).toBe('24/min')
    expect(formatRate(599)).toBe('599/min')
    expect(formatRate(0.4)).toBe('<1/min')
  })
})

describe('formatAge', () => {
  it('reports no observation rather than an age of zero', () => {
    expect(formatAge(null)).toBe(NOT_OBSERVED)
    expect(formatAge(undefined)).toBe(NOT_OBSERVED)
    expect(formatAge(0)).toBe('0s ago')
  })

  it('scales its unit', () => {
    expect(formatAge(4.2)).toBe('4s ago')
    expect(formatAge(59)).toBe('59s ago')
    expect(formatAge(99.5)).toBe('2m ago')
    expect(formatAge(9262)).toBe('3h ago')
    expect(formatAge(84360)).toBe('1d ago')
  })
})

describe('formatCount', () => {
  it('distinguishes "none" from "not counted"', () => {
    expect(formatCount(0)).toBe('0')
    expect(formatCount(null)).toBe(NOT_OBSERVED)
    expect(formatCount(undefined)).toBe(NOT_OBSERVED)
    expect(formatCount(11)).toBe('11')
  })
})

describe('flowProfile', () => {
  it('refuses to animate an edge that reports nothing', () => {
    for (const nothing of [null, undefined, 0, -3]) {
      const profile = flowProfile(nothing)
      expect(profile.moving).toBe(false)
      expect(profile.durationS).toBe(0)
    }
  })

  it('animates an edge that reports traffic', () => {
    const profile = flowProfile(24)
    expect(profile.moving).toBe(true)
    expect(profile.durationS).toBeGreaterThan(0)
  })

  it('makes a busier edge cycle faster and draw heavier', () => {
    const slow = flowProfile(8)
    const fast = flowProfile(599)
    expect(fast.durationS).toBeLessThan(slow.durationS)
    expect(fast.strokeWidth).toBeGreaterThan(slow.strokeWidth)
  })

  it('stays within the bounds the stylesheet can render', () => {
    for (const rate of [0.01, 1, 8, 24, 599, 100_000]) {
      const profile = flowProfile(rate)
      expect(profile.strokeWidth).toBeGreaterThanOrEqual(1.2)
      expect(profile.strokeWidth).toBeLessThanOrEqual(5)
      expect(profile.durationS).toBeGreaterThanOrEqual(2.2)
      expect(profile.durationS).toBeLessThanOrEqual(12)
    }
  })
})

describe('desk execution and risk formatters', () => {
  it('keeps halted, gated, and off as distinct claims', () => {
    expect(formatExecution('halted')).toBe('Halted')
    expect(formatExecution('gated')).toBe('Gated')
    expect(formatExecution('off')).toBe('Off')
    expect(formatExecution('unknown')).toBe(NOT_OBSERVED)
    expect(formatExecutionHeadline('halted')).toBe('Execution is halted.')
    expect(formatExecutionHeadline('off')).toBe('Trading stays off.')
    expect(formatExecutionHeadline('gated')).toBe('Trading is gated.')
    expect(formatExecutionHeadline(null)).toBe('Waiting for desk state.')
    expect(executionTone('halted')).toBe('ice')
    expect(executionTone('gated')).toBe('sapphire')
    expect(executionTone('off')).toBe('degraded')
  })

  it('formats posture and runway risk without inventing availability', () => {
    expect(formatPosture('capital_preservation')).toBe('Capital preservation')
    expect(formatNewRisk('restricted')).toBe('Restricted')
    expect(formatNewRisk('available')).toBe('Available')
    expect(formatNewRisk(null)).toBe(NOT_OBSERVED)
    expect(riskTone('restricted')).toBe('degraded')
    expect(riskTone('blocked')).toBe('failed')
    expect(riskTone('available')).toBe('sapphire')
  })

  it('formats signed marks with an explicit sign and no fabricated zero', () => {
    expect(formatPercent(24)).toBe('24%')
    expect(formatPercent(null)).toBe(NOT_OBSERVED)
    expect(formatSignedPercent(176.01)).toBe('+176%')
    expect(formatSignedPercent(-7.82)).toBe('-7.8%')
    expect(formatSignedPercent(null)).toBe(NOT_OBSERVED)
    expect(formatSignedPoints(183.83)).toBe('+183.8pp')
  })
})

describe('against the captured snapshot', () => {
  const snapshot = liveSnapshot()

  it('confirms the premise: no link in it reports a latency', () => {
    expect(snapshot.links.length).toBeGreaterThan(0)
    expect(snapshot.links.every((link) => link.latency_ms === null)).toBe(true)
  })

  it('formats every one of them as unmeasured', () => {
    for (const link of snapshot.links) {
      expect(formatLatency(link.latency_ms)).toBe(NOT_MEASURED)
    }
  })
})

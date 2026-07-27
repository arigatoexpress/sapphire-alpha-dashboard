import { describe, expect, it } from 'vitest'
import {
  formatAge,
  formatClockTime,
  formatCount,
  formatObservedAt,
  NOT_OBSERVED,
} from '../desk/format'

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

describe('formatObservedAt', () => {
  it('includes the date and UTC zone rather than an ambiguous clock', () => {
    expect(formatObservedAt('2026-07-27T16:31:00Z')).toBe('2026-07-27 16:31:00Z')
    expect(formatObservedAt(null)).toBe(NOT_OBSERVED)
    expect(formatObservedAt('invalid')).toBe(NOT_OBSERVED)
  })
})

describe('formatClockTime', () => {
  it('uses a clock only for compact event rows and preserves absence', () => {
    expect(formatClockTime(null)).toBe('—')
    expect(formatClockTime('invalid')).toBe('—')
    expect(formatClockTime('2026-07-27T16:31:00Z')).not.toBe('—')
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

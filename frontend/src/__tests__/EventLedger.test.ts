import { describe, expect, it } from 'vitest'
import { recentEvents } from '../App'
import type { LiveEvent } from '../types'

function event(id: string, observed_at: string): LiveEvent {
  return {
    id,
    observed_at,
    event_class: 'agent',
    source: 'intelligence',
    target: 'archive',
    label: id,
    status: 'observed',
  }
}

describe('evidence ledger ordering', () => {
  it('shows the nine newest events in newest-first order', () => {
    const events = Array.from({ length: 12 }, (_, index) => event(
      `event-${index}`,
      `2026-07-26T${String(index).padStart(2, '0')}:00:00+00:00`,
    ))
    events.reverse()
    const result = recentEvents(events)
    expect(result.map((item) => item.id)).toEqual([
      'event-11',
      'event-10',
      'event-9',
      'event-8',
      'event-7',
      'event-6',
      'event-5',
      'event-4',
      'event-3',
    ])
  })
})

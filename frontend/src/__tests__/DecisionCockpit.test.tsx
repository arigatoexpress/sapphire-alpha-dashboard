import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { DecisionCockpit } from '../components/DecisionCockpit'
import type { LiveDesk } from '../types'

const desk: LiveDesk = {
  version: 1,
  updated_at: '2026-07-26T08:00:00+00:00',
  posture: 'capital_preservation',
  leader: 'none',
  validation: { oos_pass: 0, oos_total: 7, conflicts: 1 },
  decisions: {
    pending: 0,
    pending_review: 0,
    approved_awaiting_execution: 14,
    eligible_execution: 0,
    blocked: 14,
  },
  execution: 'halted',
  feeds: { fresh: 7, total: 7 },
}

describe('decision cockpit', () => {
  const markup = renderToStaticMarkup(<DecisionCockpit desk={desk} />)

  it('answers the desk questions before exposing machine plumbing', () => {
    expect(markup).toContain('14 approved decisions are blocked.')
    expect(markup).toContain('Capital preservation')
    expect(markup).toContain('0 / 7 pass')
    expect(markup).toContain('7 / 7 current')
    expect(markup).toContain('>halted<')
    expect(markup).toContain('Awaiting review')
    expect(markup).toContain('Approved unresolved')
    expect(markup).toContain('Execution eligible')
    expect(markup).toContain('Blocked by policy')
  })

  it('keeps private and named-source detail out of the decision surface', () => {
    expect(markup).not.toMatch(/instrument|position|balance|proposal id|analyst|podcast/i)
  })

  it('states that research cannot replace the mandate', () => {
    expect(markup).toContain('cannot silently replace it')
  })
})

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { DecisionCockpit } from '../components/DecisionCockpit'
import type { LiveDesk } from '../types'

const desk: LiveDesk = {
  version: 1,
  updated_at: '2026-07-26T08:00:00+00:00',
  posture: 'capital_preservation',
  leader: 'none',
  validation: {
    oos_pass: 0,
    oos_total: 7,
    conflicts: 3,
    conflict_details: [
      {
        strategy: 'sniper',
        live_return_pct: 176.01,
        replay_return_pct: -7.82,
        gap_pp: 183.83,
      },
      {
        strategy: 'flow-follow',
        live_return_pct: -17.11,
        replay_return_pct: -99.01,
        gap_pp: 81.9,
      },
      {
        strategy: 'mean-rev',
        live_return_pct: -50.5,
        replay_return_pct: -57.56,
        gap_pp: 7.06,
      },
    ],
    replay_span_hours: 245.3,
    replay_data_through: '2026-07-22',
  },
  decisions: {
    pending: 0,
    pending_review: 0,
    approved_awaiting_execution: 14,
    eligible_execution: 0,
    blocked: 14,
    pending_policy_blocked: 1,
  },
  execution: 'halted',
  feeds: { fresh: 7, total: 7 },
  tracks: [
    {
      strategy: 'sniper',
      status: 'current',
      live_return_pct: 176.01,
      green_days: 1,
      target_days: 14,
      open_count: 0,
      data_flags: 0,
      freshness_s: 4,
    },
    {
      strategy: 'equity',
      status: 'inactive',
      live_return_pct: 0,
      green_days: 4,
      target_days: 14,
      open_count: 0,
      data_flags: 0,
      freshness_s: 120,
    },
  ],
  risk: {
    ledger_state: 'reconciled',
    realized_drawdown_pct: 24,
    drawdown_limit_pct: 25,
    budget_remaining_pct: 4,
    new_risk: 'restricted',
  },
  experiment: {
    status: 'collecting',
    qualified_days: 1,
    required_days: 14,
    last_committed_date: '2026-07-25',
    collector: 'current',
  },
}

describe('decision cockpit', () => {
  const markup = renderToStaticMarkup(<DecisionCockpit desk={desk} />)

  it('answers the desk questions before exposing machine plumbing', () => {
    expect(markup).toContain('Trading stays off.')
    expect(markup).toContain('Release conditions')
    expect(markup).toContain('13 evidence days')
    expect(markup).toContain('Positive OOS')
    expect(markup).toContain('3 conflicts')
    expect(markup).toContain('Order runway')
    expect(markup).toContain('Restricted')
    expect(markup).toContain('until every release condition')
    expect(markup).toContain('Capital preservation')
    expect(markup).toContain('0 / 7 pass')
    expect(markup).toContain('7 / 7 current')
    expect(markup).toContain('24% used')
    expect(markup).toContain('4% remains')
    expect(markup).toContain('1 / 14')
    expect(markup).toContain('Collector current')
    expect(markup).toContain('>Halted<')
    expect(markup).toContain('Awaiting review')
    expect(markup).toContain('Blocked before review')
    expect(markup).toContain('Approved, active')
    expect(markup).toContain('Execution eligible')
    expect(markup).toContain('Approved but blocked')
  })

  it('shows the evidence behind each validation conflict', () => {
    expect(markup).toContain('Live / replay audit')
    expect(markup).toContain('Replay: 245.3 hours')
    expect(markup).toContain('through Jul 22, 2026')
    expect(markup).toContain('sniper')
    expect(markup).toContain('flow-follow')
    expect(markup).toContain('mean-rev')
    expect(markup).toContain('+176% live')
    expect(markup).toContain('-7.8% replay')
    expect(markup).toContain('+183.8pp')
  })

  it('shows paper-track evidence without exposing portfolio detail', () => {
    expect(markup).toContain('Paper strategy evidence')
    expect(markup).toContain('2 reporting tracks')
    expect(markup).toContain('1 / 14')
    expect(markup).toContain('4 / 14')
    expect(markup).toContain('Replay conflict')
    expect(markup).toContain('Flat / inactive')
    expect(markup).toContain('4s ago')
    expect(markup).toContain('2m ago')
    expect(markup).toContain('strategy-status-current')
    expect(markup).toContain('strategy-status-inactive')
    expect(markup).not.toContain('strategy-rank')
  })

  it('keeps private and named-source detail out of the decision surface', () => {
    expect(markup).not.toMatch(/instrument|position|balance|proposal id|analyst|podcast/i)
  })

  it('states that research cannot replace the mandate', () => {
    expect(markup).toContain('cannot silently replace it')
  })
})

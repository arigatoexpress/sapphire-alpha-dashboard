import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import {
  ApprovalView,
  countdownLabel,
  groupDigest,
  serverAuthorityCurrent,
  serverNowFromMonotonic,
  type ApprovalBundleDTO,
} from '../ApprovalApp'

const DIGEST = '0123456789abcdef'.repeat(4)

const bundle: ApprovalBundleDTO = {
  schema_version: 'owner-approval-display/v1',
  bundle_id: 'approval-20260728-risk-trim',
  canonical_sha256: DIGEST,
  rev: 1,
  status: 'DRAFT',
  created_at: '2026-07-28T11:58:00Z',
  compiled_at: '2026-07-28T11:59:00Z',
  compile_receipt_sha256: 'c'.repeat(64),
  expires_at: '2026-07-28T12:10:00Z',
  server_time: '2026-07-28T12:00:00Z',
  creator: 'codex-approval-bundle',
  purpose_class: 'RISK_REDUCTION',
  scope: {
    environment: [`env:${'a'.repeat(64)}`, `env:${'9'.repeat(64)}`],
    account: [`acct:${'b'.repeat(64)}`, `acct:${'8'.repeat(64)}`],
    destination: [`dest:${'c'.repeat(64)}`, `dest:${'7'.repeat(64)}`],
  },
  actions: [
    {
      action_id: 'first-action',
      action_kind: 'FINANCIAL',
      atomic_group: 'risk-one',
      environment: `env:${'a'.repeat(64)}`,
      account: `acct:${'b'.repeat(64)}`,
      destination: `dest:${'c'.repeat(64)}`,
      parameters: [
        {
          name: 'reason_code',
          value: `reason:${'d'.repeat(64)}`,
          unit: 'reason-id',
        },
      ],
      units: 'CONTRACT',
      max_cost: { amount_minor: 2500, currency: 'USD', scale: 2 },
      max_slippage_bps: 20,
      target_revision_sha256: 'e'.repeat(64),
      idempotency_key: 'first-action-one-use',
      preconditions: ['quote remains current'],
      expected_effects: ['close one exact option contract'],
      verification: ['provider receipt matches the exact action'],
      rollback: ['cancellation requires a new exact authority'],
      kill_switch: 'pause before changed execution',
      residual_risks: ['the market can gap'],
      financial: {
        account: `acct:${'b'.repeat(64)}`,
        symbol: `symbol:${'f'.repeat(64)}`,
        asset: `asset:${'1'.repeat(64)}`,
        side: 'SELL',
        quantity: null,
        max_notional: { amount_minor: 5000, currency: 'USD', scale: 2 },
        order_type: 'LIMIT',
        limit_price: { amount_minor: 2500, currency: 'USD', scale: 2 },
        stop_price: { amount_minor: 2100, currency: 'USD', scale: 2 },
        time_in_force: 'DAY',
        estimated_fees: { amount_minor: 0, currency: 'USD', scale: 2 },
        max_slippage_bps: 20,
        market_hours_policy: 'REGULAR_ONLY',
      },
    },
    {
      action_id: 'second-action',
      action_kind: 'DEPLOYMENT',
      atomic_group: 'release-one',
      environment: `env:${'a'.repeat(64)}`,
      account: `acct:${'b'.repeat(64)}`,
      destination: `dest:${'c'.repeat(64)}`,
      parameters: [
        { name: 'traffic_percent', value: 100, unit: 'percent' },
      ],
      units: 'TRAFFIC_PERCENT',
      max_cost: { amount_minor: 0, currency: 'USD', scale: 2 },
      max_slippage_bps: 0,
      target_revision_sha256: '2'.repeat(64),
      idempotency_key: 'second-action-one-use',
      preconditions: ['source tree remains exact'],
      expected_effects: ['build one exact revision'],
      verification: ['deployed digest matches'],
      rollback: ['rollback is a new exact action'],
      kill_switch: 'halt before traffic drift',
      residual_risks: ['multi-step deployment is not atomic'],
      financial: null,
    },
  ],
  execution_policy: {
    failure_mode: 'INDEPENDENT_GROUPS',
    atomic_groups: ['risk-one', 'release-one'],
  },
  partial_outcome_semantics:
    'Independent groups may end PARTIAL; completed groups are never retried.',
  independent_review: {
    reviewer: 'codex-independent',
    reviewer_class: 'INDEPENDENT_AGENT',
    verdict: 'SHIP-INERTLY',
    reviewed_at: '2026-07-28T11:59:00Z',
    candidate_sha256: '3'.repeat(64),
    artifact_sha256: '4'.repeat(64),
  },
  approval_statement: `APPROVE approval-20260728-risk-trim SHA256 ${DIGEST}`,
  approval_policy: {
    approver_identity: 'ari',
    approver_class: 'HUMAN_ATTENDED',
  },
  dependency_pins: {
    pin_set_sha256: '5'.repeat(64),
    compiler_candidate_commit: '0'.repeat(40),
    compiler_candidate_tree: '1'.repeat(40),
    compiler_result_sha256: '2'.repeat(64),
    compiler_review_sha256: '3'.repeat(64),
    fleet_lease_commit: '6'.repeat(40),
    fleet_lease_tree: '7'.repeat(40),
    fleet_lease_result_sha256: '4'.repeat(64),
    fleet_lease_review_sha256: '5'.repeat(64),
    fleet_lease_version: '0.7.0',
    approval_schema_version: '3.0.0',
    approval_source_sha256: '6'.repeat(64),
    fleet_core_source_sha256: 'd'.repeat(64),
    approval_harness_commit: 'e'.repeat(40),
    approval_harness_tree: 'f'.repeat(40),
    consumer_commit: '8'.repeat(40),
    consumer_tree: '9'.repeat(40),
    consumer_result_sha256: '7'.repeat(64),
    consumer_review_sha256: 'a'.repeat(64),
    consumer_source_sha256: 'b'.repeat(64),
    task063_merged_commit: '4205e79ac53e56b03949bf266f2a3b074a651d71',
    task063_status: 'SOURCE_MERGED_INERT',
    task065_status: 'UNAVAILABLE',
    credential_enrollment_status: 'UNAVAILABLE',
    broker_reconciliation_status: 'UNAVAILABLE',
    runtime_installation_status: 'UNAVAILABLE',
    production_execution_available: 0,
  },
  eligibility: { eligible: true, reason_code: 'ELIGIBLE' },
  consumer_state: 'DISARMED',
  etag: 'b'.repeat(64),
}

describe('owner approval view', () => {
  it('renders the complete digest, immutable order, and all decision evidence', () => {
    const html = renderToStaticMarkup(
      <ApprovalView
        bundle={bundle}
        challenge={null}
        busy={false}
        message=""
        onReauthenticate={() => undefined}
        onDecision={() => undefined}
      />,
    )

    expect(html).toContain(DIGEST)
    expect(html.indexOf('first-action')).toBeLessThan(html.indexOf('second-action'))
    for (const evidence of [
      'quote remains current',
      'close one exact option contract',
      'provider receipt matches the exact action',
      'cancellation requires a new exact authority',
      'the market can gap',
      'INDEPENDENT_GROUPS',
      'SHIP-INERTLY',
      'INDEPENDENT_AGENT',
      '2026-07-28T11:59:00Z',
      '5000 minor USD',
      '2100 minor USD',
      '0 minor USD',
      '20 bps',
      'Approval is not execution',
      'Consumer disarmed',
      `env:${'9'.repeat(64)}`,
      `acct:${'8'.repeat(64)}`,
      `dest:${'7'.repeat(64)}`,
      'Quantity',
      'Not applicable',
      '4205e79ac53e56b03949bf266f2a3b074a651d71',
      'SOURCE_MERGED_INERT',
      'Task 065',
      'Credential enrollment',
      'Broker reconciliation',
      'Runtime installation',
      'Production execution',
      'UNAVAILABLE',
    ]) {
      expect(html).toContain(evidence)
    }
    expect(html).toContain(
      '<h4>Financial terms</h4><p>Not applicable</p>',
    )
    expect(html).toContain('Re-verify owner')
    expect(html).not.toContain('GO FULLY AUTONOMOUS')
    expect(html).not.toContain('Refuse bundle')
  })

  it('renders exactly one green approval and one non-green refusal after reauth', () => {
    const html = renderToStaticMarkup(
      <ApprovalView
        bundle={bundle}
        challenge={{
          csrf_challenge: 'opaque-memory-only',
          expires_at: '2026-07-28T12:00:45Z',
        }}
        busy={false}
        message=""
        onReauthenticate={() => undefined}
        onDecision={() => undefined}
      />,
    )

    expect((html.match(/GO FULLY AUTONOMOUS/g) ?? [])).toHaveLength(1)
    expect((html.match(/Refuse bundle/g) ?? [])).toHaveLength(1)
    expect((html.match(/class="decision-approve"/g) ?? [])).toHaveLength(1)
    expect((html.match(/class="decision-refuse"/g) ?? [])).toHaveLength(1)
  })

  it('renders no decision controls for every ineligible state', () => {
    for (const reason of [
      'BUNDLE_EXPIRED',
      'BUNDLE_CHANGED',
      'INDEPENDENT_REVIEW_INVALID',
      'DEPENDENCY_MISMATCH',
      'ALREADY_DECIDED',
      'CONTROL_PLANE_SELF_MODIFICATION',
      'READ_ONLY_BOOTSTRAP',
      'AUTHORITY_BOUNDARY_UNAVAILABLE',
    ]) {
      const html = renderToStaticMarkup(
        <ApprovalView
          bundle={{
            ...bundle,
            eligibility: { eligible: false, reason_code: reason },
          }}
          challenge={{
            csrf_challenge: 'must-not-enable',
            expires_at: '2026-07-28T12:00:45Z',
          }}
          busy={false}
          message=""
          onReauthenticate={() => undefined}
          onDecision={() => undefined}
        />,
      )
      expect(html).toContain(reason)
      expect(html).not.toContain('GO FULLY AUTONOMOUS')
      expect(html).not.toContain('Refuse bundle')
    }
  })

  it('renders no authority when server and challenge windows are inconsistent', () => {
    const html = renderToStaticMarkup(
      <ApprovalView
        bundle={bundle}
        challenge={{
          csrf_challenge: 'must-not-enable',
          expires_at: '2026-07-28T12:11:00Z',
        }}
        busy={false}
        message=""
        onReauthenticate={() => undefined}
        onDecision={() => undefined}
      />,
    )
    expect(html).toContain('SERVER_STATE_STALE')
    expect(html).not.toContain('GO FULLY AUTONOMOUS')
    expect(html).not.toContain('Refuse bundle')
    expect(html).not.toContain('Re-verify owner')
  })

  it('groups the hash spine without changing the copied authority', () => {
    expect(groupDigest(DIGEST)).toBe(
      '01234567 89abcdef 01234567 89abcdef 01234567 89abcdef 01234567 89abcdef',
    )
    expect(groupDigest(DIGEST).split(' ').join('')).toBe(DIGEST)
  })

  it('uses restrained UTC countdown labels', () => {
    expect(
      countdownLabel(
        '2026-07-28T12:01:00Z',
        new Date('2026-07-28T12:00:00Z'),
      ),
    ).toBe('Expires in 1 minute')
    expect(
      countdownLabel(
        '2026-07-28T12:00:09Z',
        new Date('2026-07-28T12:00:00Z'),
      ),
    ).toBe('Expires in 9 seconds')
    expect(
      countdownLabel(
        '2026-07-28T12:00:00Z',
        new Date('2026-07-28T12:00:00Z'),
      ),
    ).toBe('Expired')
  })

  it('derives time only from server UTC plus monotonic elapsed time', () => {
    expect(
      serverNowFromMonotonic('2026-07-28T12:00:00Z', 10_000, 25_500).toISOString(),
    ).toBe('2026-07-28T12:00:15.500Z')
    expect(
      serverNowFromMonotonic('2026-07-28T12:00:00Z', 25_500, 10_000).toISOString(),
    ).toBe('2026-07-28T12:00:00.000Z')
  })

  it('fails closed at stale, skewed, suspended, and boundary-second states', () => {
    const serverTime = '2026-07-28T12:00:00Z'
    const bundleExpiry = '2026-07-28T12:10:00Z'
    const challengeExpiry = '2026-07-28T12:00:45Z'
    expect(
      serverAuthorityCurrent(
        serverTime,
        bundleExpiry,
        challengeExpiry,
        new Date('2026-07-28T12:00:05Z'),
      ),
    ).toBe(true)
    expect(
      serverAuthorityCurrent(
        serverTime,
        bundleExpiry,
        challengeExpiry,
        new Date('2026-07-28T12:00:05.001Z'),
      ),
    ).toBe(false)
    expect(
      serverAuthorityCurrent(
        serverTime,
        bundleExpiry,
        '2026-07-28T12:11:00Z',
        new Date(serverTime),
      ),
    ).toBe(false)
    expect(
      serverAuthorityCurrent(
        serverTime,
        serverTime,
        null,
        new Date(serverTime),
      ),
    ).toBe(false)
    const resumed = serverNowFromMonotonic(serverTime, 1_000, 31_000)
    expect(
      serverAuthorityCurrent(serverTime, bundleExpiry, challengeExpiry, resumed),
    ).toBe(false)
  })
})

import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { FEATURED_OBSERVATION } from './metrics'

const path = resolve(
  __dirname,
  '../../content/evidence/rhchain-aapl-20260808.json',
)
const raw = readFileSync(path)
const observation = JSON.parse(raw.toString('utf8')) as Record<string, any>

describe('featured public observation projection', () => {
  it('is byte-pinned and stays aligned with rendered metrics', () => {
    expect(createHash('sha256').update(raw).digest('hex')).toBe(
      'ee712e4ecee980a602fb2b679c52ba555964ae7b281799d0672c3e10de259a04',
    )
    expect(observation.asset_pair).toBe(FEATURED_OBSERVATION.assetPair)
    expect(observation.observed_at).toBe(FEATURED_OBSERVATION.observedAt)
    expect(String(observation.chain.chain_id)).toBe(FEATURED_OBSERVATION.chainId)
    expect(String(observation.range.start_block)).toBe(
      FEATURED_OBSERVATION.range.startBlock,
    )
    expect(String(observation.range.end_block)).toBe(
      FEATURED_OBSERVATION.range.endBlock,
    )
    expect(observation.evidence.batch_receipt_sha256).toBe(
      FEATURED_OBSERVATION.receiptSha256,
    )
    expect(String(observation.observations.validated_pools)).toBe(
      FEATURED_OBSERVATION.validatedPools,
    )
    expect(String(observation.observations.events)).toBe(
      FEATURED_OBSERVATION.eventCount,
    )
    expect(observation.observations.event_types[0].replace('_', ' ')).toBe(
      FEATURED_OBSERVATION.eventType.toLowerCase(),
    )
    expect(FEATURED_OBSERVATION.finality.outcome).toBe(
      `Reconciled at depth ${observation.finality.depth}`,
    )

    const metricsSource = readFileSync(resolve(__dirname, 'metrics.ts'), 'utf8')
    expect(metricsSource).toContain(
      "import publicObservation from '../../content/evidence/rhchain-aapl-20260808.json'",
    )
  })

  it('contains no public identity, account, or position fields', () => {
    const source = raw.toString('utf8').toLowerCase()
    for (const forbidden of [
      '"wallet"',
      '"sender"',
      '"recipient"',
      '"balance"',
      '"position"',
      '"chat_id"',
      '"user_id"',
    ]) {
      expect(source).not.toContain(forbidden)
    }
  })

  it('keeps economic finality and action authority false', () => {
    expect(observation.finality.economically_finalized).toBe(false)
    expect(observation.authority.signal).toBe(false)
    expect(observation.authority.ranking).toBe(false)
    expect(observation.authority.trade).toBe(false)
  })
})

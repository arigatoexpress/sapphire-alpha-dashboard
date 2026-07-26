import { describe, expect, it } from 'vitest'

import robots from './robots'

describe('public crawler policy', () => {
  it('keeps the anonymous dashboard indexable while excluding data endpoints', () => {
    const policy = robots()
    const rules = Array.isArray(policy.rules) ? policy.rules : [policy.rules]
    const disallowed = rules.flatMap((rule) =>
      Array.isArray(rule.disallow) ? rule.disallow : rule.disallow ? [rule.disallow] : [],
    )

    expect(disallowed).not.toContain('/dashboard')
    expect(disallowed).toEqual(expect.arrayContaining(['/api/', '/vault/', '/miniapp']))
  })
})

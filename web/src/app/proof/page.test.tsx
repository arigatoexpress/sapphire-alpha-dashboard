import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Proof from './page'

const markup = renderToStaticMarkup(<Proof />)

describe('the public proof ledger', () => {
  it('explains the complete decision and execution lifecycle', () => {
    for (const stage of [
      'Observe',
      'Form intent',
      'Validate',
      'Authorize',
      'Execute',
      'Reconcile',
    ]) {
      expect(markup).toContain(stage)
    }
  })

  it('publishes operating modes and fail-closed behavior', () => {
    expect(markup).toContain('Operating modes')
    expect(markup).toContain('Free-reign (bounded autonomous)')
    expect(markup).toContain('Failure is a state, not a surprise')
    expect(markup).toContain('Replay detected')
    expect(markup).toContain('Capital cap breached')
    expect(markup).toContain('Execution blocked')
  })

  it('documents only safe public read surfaces', () => {
    for (const endpoint of [
      '/api/health',
      '/api/v1/live',
      '/api/v1/moss',
      '/api/v1/transparency',
      '/api/v1/status',
      '/api/v1/widgets',
      '/api/fleet',
      '/api/v1/vault-map',
    ]) {
      expect(markup).toContain(endpoint)
    }

    expect(markup).not.toMatch(/0x[a-f0-9]{8,}/i)
    expect(markup).not.toMatch(/\b(?:\d{1,3}\.){3}\d{1,3}\b/)
    expect(markup).not.toMatch(/\/Users\/|[A-Z]:\\Users\\/i)
  })

  it('distinguishes shipped controls from withheld detail and unmade claims', () => {
    expect(markup).toContain('What is true today')
    expect(markup).toContain('Shipped')
    expect(markup).toContain('Withheld')
    expect(markup).toContain('Not claimed')
    expect(markup).toContain('No public performance claim')
  })

  it('defines the system language instead of assuming it', () => {
    expect(markup).toContain('Working glossary')
    expect(markup).toContain('Authority envelope')
    expect(markup).toContain('Fail-closed')
    expect(markup).toContain('Reconciliation')
  })
})

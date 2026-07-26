import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { describeLink, describeNode } from '@shared/vocabulary'
import { NOT_MEASURED } from '../desk/format'
import { SignalRoutes } from '../components/SignalRoutes'
import { liveSnapshot } from './fixture'

const snapshot = liveSnapshot()

function render(overrides: Partial<Parameters<typeof SignalRoutes>[0]> = {}) {
  return renderToStaticMarkup(
    <SignalRoutes
      nodes={snapshot.nodes}
      links={snapshot.links}
      status={snapshot.status}
      {...overrides}
    />,
  )
}

describe('a legible route ledger', () => {
  const markup = render()

  it('renders one non-crossing row per declared route instead of a topology drawing', () => {
    expect(markup.match(/data-route=/g)?.length).toBe(snapshot.links.length)
    expect(markup).not.toContain('<svg')
    expect(markup).not.toContain('Signal Loom')
    expect(markup).toContain('Signal paths')
  })

  it('names both endpoints and the work on every route', () => {
    for (const link of snapshot.links) {
      expect(markup).toContain(describeNode(link.source).plainName)
      expect(markup).toContain(describeNode(link.target).plainName)
      expect(markup).toContain(describeLink(link).plainName)
    }
  })

  it('shows every reporting node once in the node inventory', () => {
    expect(markup.match(/data-node=/g)?.length).toBe(snapshot.nodes.length)
    for (const node of snapshot.nodes) expect(markup).toContain(describeNode(node.id).plainName)
  })
})

describe('measurement honesty', () => {
  it('renders null latency as words and never as a number', () => {
    const markup = render()
    expect(snapshot.links.every((link) => link.latency_ms === null)).toBe(true)
    expect(markup).not.toMatch(/\d+(\.\d+)?\s*ms/)
    expect(markup).toContain(NOT_MEASURED)
    expect(markup).toContain(`0 of ${snapshot.links.length} timed`)
  })

  it('shows a measured zero as a real measurement', () => {
    const markup = render({ links: [{ ...snapshot.links[0], latency_ms: 0 }] })
    expect(markup).toContain('0 ms')
    expect(markup).toContain('1 of 1 timed')
  })

  it('does not invent traffic for an unmeasured route', () => {
    const link = { ...snapshot.links[0], event_rate: null }
    const markup = render({
      links: [link],
      nodes: snapshot.nodes.filter((node) => node.id === link.source || node.id === link.target),
    })
    expect(markup).toContain('not measured')
    expect(markup).not.toContain('0/min')
  })
})

describe('empty and malformed input', () => {
  it('uses a compact honest empty state', () => {
    const markup = render({ nodes: [], links: [], status: 'offline' })
    expect(markup).toContain('The home machines are not reporting')
    expect(markup).not.toContain('data-route=')
    expect(markup).not.toContain('placeholder')
  })

  it('drops links whose endpoint was never declared', () => {
    const markup = render({
      links: [{ ...snapshot.links[0], target: 'nowhere-at-all' }],
    })
    expect(markup).toContain('0 of 0 timed')
    expect(markup).not.toContain('data-route=')
  })
})

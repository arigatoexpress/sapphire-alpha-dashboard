/**
 * The loom, rendered.
 *
 * `renderToStaticMarkup` gives real markup from the real component with no
 * jsdom and no testing library — one fewer dependency, and the assertions are
 * about what a reader would see rather than about which props were passed.
 * Effects do not run, so the layout uses the component's own fallback width;
 * the geometry is covered across widths in `loomGeometry.test.ts`.
 */

import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { SignalLoom } from '../components/SignalLoom'
import { describeNode } from '@shared/vocabulary'
import { NOT_MEASURED } from '../desk/format'
import { liveSnapshot } from './fixture'

const snapshot = liveSnapshot()

function render(overrides: Partial<Parameters<typeof SignalLoom>[0]> = {}) {
  return renderToStaticMarkup(
    <SignalLoom
      nodes={snapshot.nodes}
      links={snapshot.links}
      status={snapshot.status}
      {...overrides}
    />,
  )
}

describe('an unmeasured latency', () => {
  const markup = render()

  it('renders as words, once per link and never as a number', () => {
    /* Every link in the snapshot reports `latency_ms: null`. If any of them
       rendered a figure, this catches it — including a fabricated zero. */
    expect(snapshot.links.every((link) => link.latency_ms === null)).toBe(true)
    expect(markup).not.toMatch(/\d+(\.\d+)?\s*ms/)
    expect(markup).toContain(NOT_MEASURED)
  })

  it('reports how many links are actually timed, rather than implying all are', () => {
    expect(markup).toContain(`0 of ${snapshot.links.length} report a round-trip time`)
  })

  it('lights up on its own once a probe reports', () => {
    const measured = render({
      links: snapshot.links.map((link, index) =>
        index === 0 ? { ...link, latency_ms: 34.2 } : link,
      ),
    })
    expect(measured).toContain('34 ms')
    expect(measured).toContain(`1 of ${snapshot.links.length} report a round-trip time`)
    /* The other eight are still honest. */
    expect(measured).toContain(NOT_MEASURED)
  })

  it('shows a measured zero as a zero, not as unmeasured', () => {
    const zero = render({ links: [{ ...snapshot.links[0], latency_ms: 0 }] })
    expect(zero).toContain('0 ms')
    expect(zero).toContain('1 of 1 report a round-trip time')
  })
})

describe('motion', () => {
  it('animates only the edges that report traffic', () => {
    const markup = render({
      links: [
        { ...snapshot.links[0], event_rate: 0 },
        { ...snapshot.links[1], event_rate: 24 },
      ],
    })
    expect(markup).toContain('is-still')
    expect(markup).toContain('is-moving')
  })

  it('gives a silent edge a flow duration of exactly zero', () => {
    const markup = render({ links: [{ ...snapshot.links[0], event_rate: 0 }] })
    expect(markup).toContain('--flow-duration:0s')
    expect(markup).not.toContain('is-moving')
  })

  it('drives the duration from the rate, so a busy edge differs from a quiet one', () => {
    const busy = render({ links: [{ ...snapshot.links[0], event_rate: 599 }] })
    const quiet = render({ links: [{ ...snapshot.links[0], event_rate: 8 }] })
    const durationOf = (markup: string) => /--flow-duration:([\d.]+)s/.exec(markup)?.[1]
    expect(durationOf(busy)).toBeDefined()
    expect(durationOf(quiet)).toBeDefined()
    expect(Number(durationOf(busy))).toBeLessThan(Number(durationOf(quiet)))
  })
})

describe('plain English', () => {
  const markup = render()

  it('names every node the way the shared vocabulary does', () => {
    for (const node of snapshot.nodes) {
      expect(markup).toContain(describeNode(node.id).plainName)
    }
  })

  it('never falls back to a raw slug for a node it knows', () => {
    expect(markup).not.toContain('Missing description')
  })

  it('shows each node its own measured load and rate', () => {
    expect(markup).toContain('high load')
    expect(markup).toContain('599/min')
  })

  it('does not turn decorative graph marks into keyboard stops', () => {
    /* The SVG has a complete link ledger below it, so its hover-only highlight
       must not add non-interactive nodes and boxes to the tab order. */
    expect(markup).not.toContain('tabindex=')
    expect(markup).toContain('aria-label="Home desktop computer:')
    expect(markup).toContain('aria-label="Home desktop computer readings"')
  })
})

describe('nothing to draw', () => {
  it('says the machines are not reporting instead of drawing a placeholder', () => {
    const markup = render({ nodes: [], links: [], status: 'offline' })
    expect(markup).toContain('The home machines are not reporting')
    expect(markup).not.toContain('<svg class="loom"')
  })

  it('distinguishes warming from offline', () => {
    const markup = render({ nodes: [], links: [], status: 'warming' })
    expect(markup).toContain('Waiting for the first report to arrive')
  })
})

describe('links naming a node that was never declared', () => {
  it('drops them rather than drawing to the origin', () => {
    const markup = render({
      links: [{ ...snapshot.links[0], target: 'nowhere-at-all' }],
    })
    expect(markup).toContain('0 of 0 report a round-trip time')
  })
})

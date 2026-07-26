import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { NODE_VOCABULARY } from '@shared/vocabulary'
import MachineRoom, { wire, type WireBox } from './MachineRoom'

describe('Machine Room without JavaScript or a fetched response', () => {
  const html = renderToStaticMarkup(<MachineRoom />)

  it('renders the complete declared map as readable static HTML', () => {
    for (const node of Object.values(NODE_VOCABULARY)) {
      expect(html).toContain(node.plainName)
      expect(html).toContain(node.oneLiner)
    }
    expect(html).toContain('data-precision="none"')
    expect(html).toContain('Waiting for a reading')
  })

  it('prints absence rather than a plausible live figure', () => {
    expect(html.match(/not measured/g)?.length).toBeGreaterThanOrEqual(
      Object.keys(NODE_VOCABULARY).length * 2,
    )
    expect(html).not.toMatch(/about \d+ times a minute/)
    expect(html).not.toMatch(/animation-duration/)
  })

  it('has a text equivalent and a non-visual status announcement', () => {
    expect(html).toContain('Read all of this as text instead')
    expect(html).toContain('aria-live="polite"')
    expect(html).toContain('No feed detail yet')
  })

  it('does not put non-interactive map cards in the keyboard tab order', () => {
    expect(html).not.toContain('tabindex=')
  })

  it('renders the exact command that reproduces every live figure', () => {
    expect(html).toContain('Reproduce every live reading')
    expect(html).toContain('/api/v1/live')
    expect(html).toContain('curl -s https://sapphirealpha.xyz/api/v1/live | jq .')
  })
})

describe('responsive wire geometry', () => {
  const cases: Array<{
    name: string
    from: WireBox
    to: WireBox
    start: [number, number]
    end: [number, number]
  }> = [
    {
      name: 'one-column phone stack',
      from: { x: 10, y: 0, w: 280, h: 100 },
      to: { x: 10, y: 132, w: 280, h: 100 },
      start: [150, 100],
      end: [150, 132],
    },
    {
      name: 'two-column tablet row',
      from: { x: 0, y: 0, w: 280, h: 110 },
      to: { x: 310, y: 8, w: 280, h: 110 },
      start: [280, 55],
      end: [310, 63],
    },
    {
      name: 'three-column wrapped connection',
      from: { x: 310, y: 0, w: 280, h: 110 },
      to: { x: 310, y: 150, w: 280, h: 110 },
      start: [450, 110],
      end: [450, 150],
    },
    {
      name: 'five-column wide row',
      from: { x: 0, y: 0, w: 190, h: 120 },
      to: { x: 880, y: 0, w: 190, h: 120 },
      start: [190, 60],
      end: [880, 60],
    },
  ]

  it.each(cases)('joins the facing card edges in a $name', ({ from, to, start, end }) => {
    const path = wire(from, to)
    const numbers = path.match(/-?\d+(?:\.\d+)?/g)?.map(Number) ?? []

    expect(numbers).toHaveLength(8)
    expect(numbers.slice(0, 2)).toEqual(start)
    expect(numbers.slice(-2)).toEqual(end)
    expect(numbers.every(Number.isFinite)).toBe(true)
  })
})

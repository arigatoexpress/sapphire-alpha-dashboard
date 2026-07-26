/**
 * The overlap Ari reported, pinned.
 *
 * Two separate guarantees, because the old renderer broke both at once:
 * placements had to stop colliding (eleven nodes, six zones, one coordinate per
 * zone), and labels had to stop colliding (fixed `y` offsets from that one
 * coordinate). Neither is checkable by looking at one window size, which is how
 * both survived.
 */

import { describe, expect, it } from 'vitest'
import { loomGeometry, type LoomGeometry } from '../desk/loomGeometry'
import { describeNode } from '@shared/vocabulary'
import type { LoomBox } from '@shared/loomLayout'
import { liveSnapshot } from './fixture'

const snapshot = liveSnapshot()
const NODES = snapshot.nodes
/* 240 and 272 cover the loom's actual content box on very narrow phones; the
   wider values pin tablet, laptop and large-monitor layouts. */
const WIDTHS = [240, 272, 320, 480, 768, 1024, 1440, 1920]

function overlaps(a: LoomBox, b: LoomBox): boolean {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height
}

function collidingBoxes(geometry: LoomGeometry): string[] {
  const hits: string[] = []
  for (let i = 0; i < geometry.boxes.length; i += 1) {
    for (let j = i + 1; j < geometry.boxes.length; j += 1) {
      if (overlaps(geometry.boxes[i], geometry.boxes[j])) {
        hits.push(`${geometry.boxes[i].id} ∩ ${geometry.boxes[j].id}`)
      }
    }
  }
  return hits
}

describe('the fixture is the hard case', () => {
  it('has several nodes sharing a zone', () => {
    const perZone = new Map<string, number>()
    for (const node of NODES) perZone.set(node.zone, (perZone.get(node.zone) ?? 0) + 1)
    expect(Math.max(...perZone.values())).toBeGreaterThanOrEqual(3)
    expect(NODES.length).toBeGreaterThan(perZone.size)
  })
})

describe.each(WIDTHS)('at %ipx', (width) => {
  const geometry = loomGeometry(NODES, { width })

  it('gives every node its own point, including within a shared zone', () => {
    const collisions: string[] = []
    for (let i = 0; i < geometry.placements.length; i += 1) {
      for (let j = i + 1; j < geometry.placements.length; j += 1) {
        const a = geometry.placements[i]
        const b = geometry.placements[j]
        const distance = Math.hypot(a.point.x - b.point.x, a.point.y - b.point.y)
        if (distance < 12) collisions.push(`${a.node.id} ↔ ${b.node.id} (${distance.toFixed(1)})`)
      }
    }
    expect(collisions).toEqual([])
  })

  it('overlaps no two label boxes', () => {
    expect(collidingBoxes(geometry)).toEqual([])
  })

  it('names every node exactly once', () => {
    expect(geometry.boxes.map((box) => box.id).sort()).toEqual(NODES.map((node) => node.id).sort())
  })

  it('keeps every label box inside the drawing', () => {
    for (const box of geometry.boxes) {
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(geometry.width + 0.001)
      expect(box.y).toBeGreaterThanOrEqual(geometry.graphHeight)
      expect(box.y + box.height).toBeLessThanOrEqual(geometry.height + 0.001)
    }
  })

  it('keeps every node inside the graph band', () => {
    for (const { point } of geometry.placements) {
      expect(point.x).toBeGreaterThanOrEqual(0)
      expect(point.x).toBeLessThanOrEqual(geometry.width)
      expect(point.y).toBeGreaterThanOrEqual(0)
      expect(point.y).toBeLessThanOrEqual(geometry.graphHeight)
    }
  })

  it('anchors each label on the node it names', () => {
    for (const box of geometry.boxes) {
      expect(box.anchor).toEqual(geometry.points[box.id])
    }
  })
})

describe('label content', () => {
  const geometry = loomGeometry(NODES, { width: 900 })

  it('uses the shared plain-English name, never a raw id', () => {
    for (const node of NODES) {
      const box = geometry.boxes.find((candidate) => candidate.id === node.id)!
      const label = box.lines
        .filter((line) => line.kind === 'label')
        .map((line) => line.text)
        .join(' ')
      expect(label).toBe(describeNode(node.id).plainName)
      /* A raw slug is all lowercase, digits and hyphens. A plain name never is. */
      expect(label).not.toBe(node.id)
      expect(label).not.toMatch(/^[a-z0-9-]+$/)
    }
  })

  it('puts measured readings in the subtext', () => {
    const box = geometry.boxes.find((candidate) => candidate.id === 'markets')!
    const subtext = box.lines
      .filter((line) => line.kind === 'subtext')
      .map((line) => line.text)
      .join(' ')
    expect(subtext).toContain('599/min')
    expect(subtext).toContain('high load')
  })
})

describe('degenerate inputs', () => {
  it('lays out nothing without throwing', () => {
    const geometry = loomGeometry([], { width: 900 })
    expect(geometry.boxes).toEqual([])
    expect(geometry.placements).toEqual([])
  })

  it('survives a width of zero', () => {
    const geometry = loomGeometry(NODES, { width: 0 })
    expect(collidingBoxes(geometry)).toEqual([])
  })
})

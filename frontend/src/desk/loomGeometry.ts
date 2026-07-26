/**
 * Where everything on the Signal Loom goes. Pure: nodes and a width in, numbers
 * out. No DOM, no React, no measurement of a live font.
 *
 * Two separate problems, and the old renderer conflated them:
 *
 * 1. **Node placement.** `SignalLoom` used to map *zone* to a point, and eleven
 *    nodes share six zones — `compute` alone holds three. Every node in a zone
 *    was drawn at the identical coordinate, and so was its label and its
 *    subtext. That is the overlap Ari reported, and no amount of nudging a
 *    `y="43"` offset fixes it, because the collision is between nodes rather
 *    than between a label and its own subtext. Here each node in a zone gets its
 *    own point on a vertical fan, so two nodes cannot share a coordinate.
 *
 * 2. **Label placement.** Deferred wholesale to `@shared/loomLayout`, whose
 *    non-overlap guarantee is structural (row packing) and is unit-tested at
 *    320 / 768 / 1440 with worst-case label text. Nothing here re-positions a
 *    box afterwards; the field is translated as a whole by `fieldTop`, which is
 *    a rigid motion and so preserves the guarantee.
 *
 * One user unit is one CSS pixel: the renderer sets `viewBox` from the measured
 * container width. That is what lets `loomLayout`'s pixel metrics mean anything
 * — a fixed viewBox would scale the type out from under them.
 */

import { loomLayout, type LoomBox, type LoomLabelInput, type LoomMetrics } from '@shared/loomLayout'
import { describeNode } from '@shared/vocabulary'
import type { LiveNode, Zone } from '@shared/telemetry'
import { formatAge, formatRate } from './format'

export interface LoomPoint {
  x: number
  y: number
}

export interface LoomNodePlacement {
  node: LiveNode
  point: LoomPoint
}

export interface LoomGeometry {
  width: number
  /** Total SVG height: graph band, gap, then the label field. */
  height: number
  /** Height of the band the graph itself occupies. */
  graphHeight: number
  /** Y offset applied to every label box. */
  fieldTop: number
  nodeRadius: number
  haloRadius: number
  placements: LoomNodePlacement[]
  points: Record<string, LoomPoint>
  /** Absolute label boxes, already translated into the field. */
  boxes: LoomBox[]
}

/**
 * Zone anchors. `fx` is the column a zone sits in, as a fraction of the
 * drawable width; reading order is left to right — the outside world, then the
 * scheduler, then the machines, then what they produce. `fy` orders zones that
 * share a column, and nothing else: it is not a position.
 *
 * `compute` and `intelligence` share a column deliberately, as do `markets`
 * and `archive`. Anything sharing a column shares one ladder of rows, which is
 * what keeps them apart — see `placeNodes`.
 */
const ZONE_ANCHORS: Record<Zone, { fx: number; fy: number }> = {
  edge: { fx: 0.0, fy: 0.5 },
  orchestration: { fx: 0.26, fy: 0.2 },
  compute: { fx: 0.55, fy: 0.24 },
  intelligence: { fx: 0.55, fy: 0.8 },
  markets: { fx: 1.0, fy: 0.3 },
  archive: { fx: 1.0, fy: 0.84 },
}

const FALLBACK_ANCHOR = { fx: 0.5, fy: 0.5 }

/** Column x fractions, deduplicated and ordered, so the grid is stable. */
const COLUMN_FRACTIONS = [...new Set(Object.values(ZONE_ANCHORS).map((a) => a.fx))].sort(
  (a, b) => a - b,
)

/**
 * Below this much drawable width the columns are too close together to keep
 * nodes apart horizontally, so the graph collapses to a single stack. A phone
 * gets a readable vertical ladder instead of a pile.
 */
const MIN_COLUMN_SPAN = 120

function anchorFor(zone: Zone): { fx: number; fy: number } {
  return ZONE_ANCHORS[zone] ?? FALLBACK_ANCHOR
}

/**
 * Put every node on a grid of columns and rows.
 *
 * Two nodes can only coincide if they share both a column and a row, and no
 * two nodes in a column are given the same row — so they cannot. That is the
 * whole argument, and it does not depend on the width, on how many nodes share
 * a zone, or on any tuned offset. The previous renderer had no such argument:
 * it mapped zone to a point and drew three `compute` nodes on top of one
 * another.
 */
function placeNodes(
  nodes: LiveNode[],
  bounds: { marginX: number; marginY: number; spanX: number; spanY: number; width: number },
): LoomNodePlacement[] {
  if (nodes.length === 0) return []

  const stacked = bounds.spanX < MIN_COLUMN_SPAN
  const columnOf = (zone: Zone) =>
    stacked ? 0 : COLUMN_FRACTIONS.indexOf(anchorFor(zone).fx)

  const buckets = new Map<number, LiveNode[]>()
  const ordered = nodes
    .map((node, index) => ({ node, index }))
    .sort((a, b) => {
      const columnDelta = columnOf(a.node.zone) - columnOf(b.node.zone)
      if (columnDelta !== 0) return columnDelta
      const fyDelta = anchorFor(a.node.zone).fy - anchorFor(b.node.zone).fy
      if (fyDelta !== 0) return fyDelta
      return a.index - b.index
    })

  for (const { node } of ordered) {
    const column = columnOf(node.zone)
    const bucket = buckets.get(column)
    if (bucket) bucket.push(node)
    else buckets.set(column, [node])
  }

  const rows = Math.max(...[...buckets.values()].map((bucket) => bucket.length))
  const rowSpacing = rows > 1 ? bounds.spanY / (rows - 1) : 0
  const rowY = (row: number) =>
    rows > 1 ? bounds.marginY + row * rowSpacing : bounds.marginY + bounds.spanY / 2

  const placements: LoomNodePlacement[] = []
  for (const [column, bucket] of [...buckets.entries()].sort((a, b) => a[0] - b[0])) {
    const x = stacked
      ? bounds.width / 2
      : bounds.marginX + COLUMN_FRACTIONS[column] * bounds.spanX
    /* Short columns are centred in the grid rather than pinned to the top, so
       the graph reads as a fan rather than as a ragged left edge. */
    const firstRow = Math.floor((rows - bucket.length) / 2)
    bucket.forEach((node, offset) => {
      placements.push({ node, point: { x, y: rowY(firstRow + offset) } })
    })
  }

  return placements
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value))
}

/** Subtext under a node's plain name. Every part of it is a measured field. */
function nodeSubtext(node: LiveNode): string {
  return `${node.load} load · ${formatRate(node.activity_rate)} · ${formatAge(node.freshness_s)}`
}

export interface LoomGeometryOptions {
  width: number
  metrics?: Partial<LoomMetrics>
}

export function loomGeometry(nodes: LiveNode[], options: LoomGeometryOptions): LoomGeometry {
  const width = Math.max(1, options.width)

  /* The graph scales with the container instead of living in a fixed viewBox,
     so the same code is legible at 320 and at 1440. */
  const marginX = clamp(width * 0.09, 22, 76)
  const graphHeight = clamp(width * 0.42, 210, 380)
  const marginY = clamp(graphHeight * 0.12, 22, 46)
  const haloRadius = clamp(width / 26, 11, 34)
  const nodeRadius = clamp(haloRadius / 5, 3, 7)

  const spanX = Math.max(0, width - marginX * 2)
  const spanY = Math.max(0, graphHeight - marginY * 2)

  const placements = placeNodes(nodes, { marginX, marginY, spanX, spanY, width })
  const points: Record<string, LoomPoint> = {}
  for (const { node, point } of placements) points[node.id] = point

  const labels: LoomLabelInput[] = placements.map(({ node, point }) => ({
    id: node.id,
    text: describeNode(node.id).plainName,
    subtext: nodeSubtext(node),
    anchor: point,
  }))

  const fieldGap = 26
  const fieldTop = graphHeight + fieldGap
  const layout = loomLayout(labels, { width, metrics: options.metrics })
  const boxes = layout.boxes.map((box) => ({ ...box, y: box.y + fieldTop }))

  return {
    width,
    height: fieldTop + layout.height,
    graphHeight,
    fieldTop,
    nodeRadius,
    haloRadius,
    placements,
    points,
    boxes,
  }
}

/** Cubic curve between two points, bending horizontally. */
export function loomCurve(source: LoomPoint, target: LoomPoint): string {
  const bend = Math.max(36, Math.abs(target.x - source.x) * 0.42)
  return `M ${round(source.x)} ${round(source.y)} C ${round(source.x + bend)} ${round(source.y)}, ${round(
    target.x - bend,
  )} ${round(target.y)}, ${round(target.x)} ${round(target.y)}`
}

/** Leader line from a node to the top edge of the box that names it. */
export function leaderPath(anchor: LoomPoint, box: LoomBox): string {
  const headX = box.x + box.width / 2
  const headY = box.y
  const midY = (anchor.y + headY) / 2
  return `M ${round(anchor.x)} ${round(anchor.y)} C ${round(anchor.x)} ${round(midY)}, ${round(
    headX,
  )} ${round(midY)}, ${round(headX)} ${round(headY)}`
}

function round(value: number): number {
  return Math.round(value * 100) / 100
}

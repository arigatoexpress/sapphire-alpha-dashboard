/**
 * Label placement for the signal loom. Pure: text in, boxes out. No DOM, no
 * measurement of a live font, no browser.
 *
 * Why this exists: the loom positions nodes by *zone*, and several nodes share a
 * zone — three of them share `compute` today. Their labels and subtexts are
 * drawn at fixed offsets from the same point, so they land on top of each other,
 * and they collide differently at every container width. Eyeballing one window
 * size cannot fix that.
 *
 * The guarantee here is structural rather than incidental: boxes are packed into
 * horizontal rows, rows never share vertical space, and within a row boxes are
 * laid left to right with a gap. Two boxes therefore cannot overlap, at any
 * width, for any label text. `shared/__tests__/loomLayout.test.ts` asserts it
 * pairwise anyway.
 *
 * Anchors are respected as *ordering*, not as position: boxes are emitted top
 * row first, then left to right, following the anchors they were given, so the
 * laid-out labels keep the reading order of the graph they describe. A renderer
 * draws a leader line from each box back to `box.anchor`.
 */

export interface LoomLabelInput {
  id: string
  text: string
  subtext?: string
  /** Where this label belongs in the diagram. Used for ordering only. */
  anchor?: { x: number; y: number }
}

export interface LoomMetrics {
  /** Estimated advance width of one character of label text. */
  charWidthPx: number
  lineHeightPx: number
  /** Estimated advance width of one character of subtext. */
  subtextCharWidthPx: number
  subtextLineHeightPx: number
  paddingXPx: number
  paddingYPx: number
  /** Horizontal gap between two boxes in the same row. */
  gapXPx: number
  /** Vertical gap between rows. */
  gapYPx: number
  /** A box never gets wider than this, however long the text is. */
  maxTextWidthPx: number
}

/**
 * Conservative estimates for the loom's type (JetBrains Mono / Inter at the
 * sizes `index.css` uses). Over-estimating a character is safe — it produces
 * slightly roomy boxes; under-estimating would produce overlap, so these lean
 * wide on purpose. A renderer that uses different type passes its own metrics.
 */
export const DEFAULT_LOOM_METRICS: LoomMetrics = {
  charWidthPx: 7.6,
  lineHeightPx: 16,
  subtextCharWidthPx: 6.2,
  subtextLineHeightPx: 14,
  paddingXPx: 8,
  paddingYPx: 6,
  gapXPx: 12,
  gapYPx: 10,
  maxTextWidthPx: 240,
}

export type LoomLineKind = 'label' | 'subtext'

export interface LoomLine {
  text: string
  kind: LoomLineKind
  /** Offset of this line's top edge from the box's top edge. */
  y: number
  height: number
}

export interface LoomBox {
  id: string
  x: number
  y: number
  width: number
  height: number
  lines: LoomLine[]
  row: number
  anchor: { x: number; y: number } | null
}

export interface LoomLayout {
  boxes: LoomBox[]
  width: number
  height: number
  rows: number
}

export interface LoomLayoutOptions {
  /** Container width in pixels. */
  width: number
  metrics?: Partial<LoomMetrics>
}

/** Greedy word wrap against an estimated character width. Never splits a word. */
function wrap(text: string, maxWidth: number, charWidth: number): string[] {
  const words = text.split(/\s+/).filter(Boolean)
  if (words.length === 0) return []
  const lines: string[] = []
  let current = words[0]
  for (const word of words.slice(1)) {
    const candidate = `${current} ${word}`
    if (candidate.length * charWidth <= maxWidth) {
      current = candidate
    } else {
      lines.push(current)
      current = word
    }
  }
  lines.push(current)
  return lines
}

export function loomLayout(labels: LoomLabelInput[], options: LoomLayoutOptions): LoomLayout {
  const metrics: LoomMetrics = { ...DEFAULT_LOOM_METRICS, ...options.metrics }
  const width = options.width

  if (labels.length === 0) {
    return { boxes: [], width, height: 0, rows: 0 }
  }

  /* At least one character must fit per line, or wrapping would not terminate. */
  const innerWidth = Math.max(
    metrics.charWidthPx,
    metrics.subtextCharWidthPx,
    Math.min(metrics.maxTextWidthPx, width - metrics.paddingXPx * 2),
  )

  /* Anchor is an ordering hint. Sort is stable on id so the output is
     deterministic even when two labels share an anchor exactly. */
  const ordered = labels
    .map((label, index) => ({ label, index }))
    .sort((a, b) => {
      const ay = a.label.anchor?.y ?? 0
      const by = b.label.anchor?.y ?? 0
      if (ay !== by) return ay - by
      const ax = a.label.anchor?.x ?? 0
      const bx = b.label.anchor?.x ?? 0
      if (ax !== bx) return ax - bx
      return a.index - b.index
    })

  const measured = ordered.map(({ label }) => {
    const labelLines = wrap(label.text, innerWidth, metrics.charWidthPx)
    const subtextLines = label.subtext ? wrap(label.subtext, innerWidth, metrics.subtextCharWidthPx) : []

    const textWidth = Math.max(
      0,
      ...labelLines.map((line) => line.length * metrics.charWidthPx),
      ...subtextLines.map((line) => line.length * metrics.subtextCharWidthPx),
    )

    const lines: LoomLine[] = []
    let cursor = metrics.paddingYPx
    for (const text of labelLines) {
      lines.push({ text, kind: 'label', y: cursor, height: metrics.lineHeightPx })
      cursor += metrics.lineHeightPx
    }
    for (const text of subtextLines) {
      lines.push({ text, kind: 'subtext', y: cursor, height: metrics.subtextLineHeightPx })
      cursor += metrics.subtextLineHeightPx
    }

    return {
      label,
      lines,
      width: Math.min(width, Math.ceil(textWidth + metrics.paddingXPx * 2)),
      height: Math.ceil(cursor + metrics.paddingYPx),
    }
  })

  /* Row packing. A row is closed as soon as the next box would cross `width`,
     and the next row starts below the tallest box in the closed one — so no two
     boxes can share both an x span and a y span. */
  const boxes: LoomBox[] = []
  let row = 0
  let cursorX = 0
  let rowTop = 0
  let rowHeight = 0

  for (const item of measured) {
    const needsNewRow = cursorX > 0 && cursorX + item.width > width
    if (needsNewRow) {
      rowTop += rowHeight + metrics.gapYPx
      row += 1
      cursorX = 0
      rowHeight = 0
    }
    boxes.push({
      id: item.label.id,
      x: cursorX,
      y: rowTop,
      width: item.width,
      height: item.height,
      lines: item.lines,
      row,
      anchor: item.label.anchor ? { ...item.label.anchor } : null,
    })
    cursorX += item.width + metrics.gapXPx
    rowHeight = Math.max(rowHeight, item.height)
  }

  return { boxes, width, height: rowTop + rowHeight, rows: row + 1 }
}

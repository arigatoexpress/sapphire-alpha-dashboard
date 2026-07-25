import { describe, expect, it } from 'vitest'
import { DEFAULT_LOOM_METRICS, loomLayout, type LoomBox, type LoomLabelInput } from '../loomLayout'
import type { LiveSnapshot } from '../telemetry'
import { describeNode } from '../vocabulary'
import realSnapshot from './fixtures/live-snapshot.json'

const WIDTHS = [320, 768, 1440]

/* Two boxes intersect if they overlap on BOTH axes. Touching edges is allowed;
   a shared boundary is not an overlap. */
function intersects(a: LoomBox, b: LoomBox): boolean {
  const xOverlap = a.x < b.x + b.width && b.x < a.x + a.width
  const yOverlap = a.y < b.y + b.height && b.y < a.y + a.height
  return xOverlap && yOverlap
}

function assertNoOverlap(boxes: LoomBox[]): void {
  for (let i = 0; i < boxes.length; i += 1) {
    for (let j = i + 1; j < boxes.length; j += 1) {
      const a = boxes[i]
      const b = boxes[j]
      if (intersects(a, b)) {
        throw new Error(
          `boxes overlap: ${a.id} [${a.x},${a.y},${a.width}x${a.height}] and ` +
            `${b.id} [${b.x},${b.y},${b.width}x${b.height}]`,
        )
      }
    }
  }
}

/* The label set that actually breaks the current SignalLoom: three compute
   nodes share one zone coordinate, so their labels and subtexts land on top of
   each other. Worst case is the longest label the schema allows (64 chars) with
   the longest subtext (120 chars). */
const WORST_CASE: LoomLabelInput[] = [
  {
    id: 'gpu-compute',
    text: 'Windows workhorse graphics card running local models continuously',
    subtext:
      'Answers questions from the trading desk and the writing agents without sending anything to an outside company at all',
    anchor: { x: 495, y: 84 },
  },
  {
    id: 'ollama-inference',
    text: 'Local model runner answering every request on this machine',
    subtext: 'Loads and unloads the language models the agents ask for, one at a time, on the home machine downstairs',
    anchor: { x: 495, y: 84 },
  },
  {
    id: 'win-workhorse',
    text: 'The home desktop computer that does the heavy lifting',
    subtext: 'Stays awake so the rest of the system has somewhere to send work at any hour of the day or night',
    anchor: { x: 495, y: 84 },
  },
  { id: 'markets', text: 'Trading desk', subtext: 'Watches prices', anchor: { x: 725, y: 155 } },
  { id: 'a', text: 'A', anchor: { x: 85, y: 220 } },
]

describe('loomLayout — non-intersection', () => {
  for (const width of WIDTHS) {
    it(`returns non-overlapping boxes at ${width}px with worst-case labels`, () => {
      const { boxes } = loomLayout(WORST_CASE, { width })
      expect(boxes).toHaveLength(WORST_CASE.length)
      assertNoOverlap(boxes)
    })

    it(`keeps every box inside the container at ${width}px`, () => {
      const layout = loomLayout(WORST_CASE, { width })
      for (const box of layout.boxes) {
        expect(box.x).toBeGreaterThanOrEqual(0)
        expect(box.y).toBeGreaterThanOrEqual(0)
        expect(box.x + box.width).toBeLessThanOrEqual(width)
        expect(box.y + box.height).toBeLessThanOrEqual(layout.height)
      }
    })

    it(`lays out every node of the real snapshot without overlap at ${width}px`, () => {
      const snapshot = realSnapshot as unknown as LiveSnapshot
      const labels: LoomLabelInput[] = snapshot.nodes.map((node, index) => {
        const described = describeNode(node.id)
        return {
          id: node.id,
          text: described.plainName,
          subtext: described.oneLiner,
          anchor: { x: (index % 4) * 220 + 60, y: Math.floor(index / 4) * 120 + 40 },
        }
      })
      assertNoOverlap(loomLayout(labels, { width }).boxes)
    })
  }

  it('does not overlap even when every label is identical and maximal', () => {
    const text = 'W'.repeat(64)
    const subtext = 'W'.repeat(120)
    const labels: LoomLabelInput[] = Array.from({ length: 24 }, (_, i) => ({
      id: `n${i}`,
      text,
      subtext,
      anchor: { x: 400, y: 200 },
    }))
    for (const width of WIDTHS) {
      assertNoOverlap(loomLayout(labels, { width }).boxes)
    }
  })

  it('does not overlap at absurdly narrow widths', () => {
    for (const width of [1, 12, 40, 120]) {
      assertNoOverlap(loomLayout(WORST_CASE, { width }).boxes)
    }
  })

  /* A box wider than its container overflows the panel and lands on whatever is
     beside it, which is the same bug wearing a different hat. */
  it('never returns a box wider than the container, at any width', () => {
    for (const width of [1, 12, 40, 120, ...WIDTHS, 4000]) {
      for (const box of loomLayout(WORST_CASE, { width }).boxes) {
        expect(box.width, `width=${width} box=${box.id}`).toBeLessThanOrEqual(width)
      }
    }
  })
})

describe('loomLayout — determinism and purity', () => {
  it('returns identical output for identical input', () => {
    expect(loomLayout(WORST_CASE, { width: 768 })).toEqual(loomLayout(WORST_CASE, { width: 768 }))
  })

  it('does not mutate its inputs', () => {
    const input: LoomLabelInput[] = JSON.parse(JSON.stringify(WORST_CASE))
    const before = JSON.stringify(input)
    loomLayout(input, { width: 768 })
    expect(JSON.stringify(input)).toBe(before)
  })

  it('handles an empty label list', () => {
    expect(loomLayout([], { width: 768 })).toEqual({ boxes: [], width: 768, height: 0, rows: 0 })
  })

  it('orders boxes by anchor, top row first, then left to right', () => {
    const labels: LoomLabelInput[] = [
      { id: 'lower', text: 'Lower', anchor: { x: 10, y: 300 } },
      { id: 'upper-right', text: 'Upper right', anchor: { x: 700, y: 10 } },
      { id: 'upper-left', text: 'Upper left', anchor: { x: 10, y: 10 } },
    ]
    expect(loomLayout(labels, { width: 1440 }).boxes.map((b) => b.id)).toEqual([
      'upper-left',
      'upper-right',
      'lower',
    ])
  })
})

describe('loomLayout — text measurement', () => {
  it('wraps long text into several lines rather than one wide box', () => {
    const [box] = loomLayout([{ id: 'x', text: WORST_CASE[0].text }], { width: 320 }).boxes
    expect(box.lines.length).toBeGreaterThan(1)
    expect(box.width).toBeLessThanOrEqual(320)
  })

  it('gives a taller box to a label that carries a subtext', () => {
    const bare = loomLayout([{ id: 'x', text: 'Trading desk' }], { width: 768 }).boxes[0]
    const withSub = loomLayout([{ id: 'x', text: 'Trading desk', subtext: 'Watches prices' }], { width: 768 }).boxes[0]
    expect(withSub.height).toBeGreaterThan(bare.height)
  })

  it('does not wrap text that fits on one line', () => {
    const box = loomLayout([{ id: 'x', text: 'Trading desk', subtext: 'Watches live prices' }], {
      width: 768,
    }).boxes[0]
    expect(box.lines.map((line) => line.text)).toEqual(['Trading desk', 'Watches live prices'])
  })

  it('fills each line up to the measured width before wrapping', () => {
    const metrics = { charWidthPx: 10, maxTextWidthPx: 100, paddingXPx: 0 }
    // 10px per char, 100px of room => 10 characters per line.
    const box = loomLayout([{ id: 'x', text: 'aaa bbb ccc ddd' }], { width: 400, metrics }).boxes[0]
    expect(box.lines.map((line) => line.text)).toEqual(['aaa bbb', 'ccc ddd'])
  })

  it('never breaks a word across lines', () => {
    const box = loomLayout([{ id: 'x', text: 'Knowledge archive search' }], { width: 320 }).boxes[0]
    const rejoined = box.lines.map((line) => line.text).join(' ')
    expect(rejoined).toBe('Knowledge archive search')
  })

  it('exposes the metrics it measured with, so a renderer can match them', () => {
    expect(DEFAULT_LOOM_METRICS.charWidthPx).toBeGreaterThan(0)
    expect(DEFAULT_LOOM_METRICS.lineHeightPx).toBeGreaterThan(0)
  })

  it('honours overridden metrics', () => {
    const wide = loomLayout([{ id: 'x', text: 'Trading desk' }], {
      width: 768,
      metrics: { charWidthPx: 20 },
    }).boxes[0]
    const narrow = loomLayout([{ id: 'x', text: 'Trading desk' }], { width: 768 }).boxes[0]
    expect(wide.width).toBeGreaterThan(narrow.width)
  })
})

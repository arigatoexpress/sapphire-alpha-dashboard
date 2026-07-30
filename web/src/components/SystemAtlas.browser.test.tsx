import { execFileSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { afterAll, describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import type { LiveSnapshot } from '@shared/telemetry'
import liveFixture from '../../../shared/__tests__/fixtures/live-snapshot.json'
import SystemAtlas from './SystemAtlas'

type LayoutResult = {
  clientWidth: number
  scrollWidth: number
  contained: boolean
  emptyBeforeTechnical: boolean
  intersections: string[]
  rectangles: Array<{ name: string; left: number; right: number; top: number; bottom: number }>
  map: { left: number; right: number; top: number; bottom: number }
}

const temp = mkdtempSync(join(tmpdir(), 'sapphire-atlas-layout-'))
const live = liveFixture as LiveSnapshot
const maxNodes = Array.from({ length: 24 }, (_value, index) => {
  const source = live.nodes[index % live.nodes.length]
  return {
    ...source,
    id: `node-${String(index + 1).padStart(2, '0')}`,
    label: `Runtime node ${index + 1}`,
  }
})
const maxSnapshot: LiveSnapshot = {
  ...structuredClone(live),
  nodes: maxNodes,
  links: maxNodes.slice(1).map((node, index) => ({
    ...live.links[index % live.links.length],
    source: maxNodes[index].id,
    target: node.id,
  })),
}

afterAll(() => rmSync(temp, { recursive: true, force: true }))

function chromePath() {
  const candidates = [
    process.env.CHROME_BIN,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ].filter((candidate): candidate is string => Boolean(candidate))
  const found = candidates.find(existsSync)
  if (!found) throw new Error('Chrome is required for atlas geometry goldens')
  return found
}

function renderAt(
  width: number,
  snapshot: LiveSnapshot | null = live,
  openTechnical = false,
): LayoutResult {
  const css = readFileSync(resolve(__dirname, '../app/globals.css'), 'utf8')
  let markup = renderToStaticMarkup(<SystemAtlas snapshot={snapshot} />)
  if (openTechnical) markup = markup.replace('<details ', '<details open="" ')
  const fixture = join(temp, `atlas-${width}.html`)
  writeFileSync(
    fixture,
    `<!doctype html>
<html>
  <head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
      :root {
        --color-glacier: #F3F8F7;
        --color-raised: #ffffff;
        --color-ink: #102A36;
        --color-ink-dim: #3A5560;
        --color-ink-faint: #6B848E;
        --color-atlas-blue: #174A67;
        --color-signal-coral: #E86F51;
        --color-skywash: #D8EBEE;
        --color-line: #C5D6DA;
        --color-line-lit: #174A67;
        --font-display: Georgia, serif;
        --font-body: Arial, sans-serif;
        --font-mono: monospace;
      }
      *, ::before, ::after { box-sizing: border-box; }
      body, h1, h2, h3, p, figure, ol, ul, dl, dd { margin: 0; }
      ol, ul { padding: 0; }
      html { overflow-x: hidden; }
      body {
        width: ${width}px;
        min-width: 0;
        margin: 0;
        overflow-x: hidden;
        font-family: var(--font-body);
      }
      ${css}
      *, *::before, *::after { animation: none !important; transition: none !important; }
    </style>
  </head>
  <body>
    ${markup}
    <script>
      const map = document.querySelector('.system-atlas__map').getBoundingClientRect();
      const cards = [...document.querySelectorAll('.system-atlas__node')].map((node) => ({
        name: node.querySelector('h3').textContent,
        rect: node.getBoundingClientRect(),
      }));
      const intersections = [];
      for (let i = 0; i < cards.length; i += 1) {
        for (let j = i + 1; j < cards.length; j += 1) {
          const a = cards[i].rect;
          const b = cards[j].rect;
          if (a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top) {
            intersections.push(cards[i].name + ' × ' + cards[j].name);
          }
        }
      }
      const contained = cards.every(({ rect }) =>
        rect.left >= map.left - 0.5 &&
        rect.right <= map.right + 0.5 &&
        rect.top >= map.top - 0.5 &&
        rect.bottom <= map.bottom + 0.5
      );
      const empty = document.querySelector('.system-atlas__empty')?.getBoundingClientRect();
      const technical = document.querySelector('.system-atlas__technical')?.getBoundingClientRect();
      const result = {
        clientWidth: document.body.clientWidth,
        scrollWidth: document.body.scrollWidth,
        contained,
        emptyBeforeTechnical: !empty || !technical || empty.bottom <= technical.top + 0.5,
        intersections,
        map: { left: map.left, right: map.right, top: map.top, bottom: map.bottom },
        rectangles: cards.map(({ name, rect }) => ({
          name,
          left: rect.left,
          right: rect.right,
          top: rect.top,
          bottom: rect.bottom,
        })),
      };
      document.body.dataset.layoutResults = encodeURIComponent(JSON.stringify(result));
    </script>
  </body>
</html>`,
  )

  const dom = execFileSync(
    chromePath(),
    [
      '--headless=new',
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--disable-background-networking',
      '--no-first-run',
      '--hide-scrollbars',
      '--no-sandbox',
      '--run-all-compositor-stages-before-draw',
      '--virtual-time-budget=1000',
      `--window-size=${Math.max(width, 500)},1100`,
      '--dump-dom',
      `file://${fixture}`,
    ],
    { encoding: 'utf8', timeout: 60_000, stdio: ['ignore', 'pipe', 'ignore'] },
  )
  const encoded = dom.match(/data-layout-results="([^"]+)"/)?.[1]
  if (!encoded) throw new Error(`Chrome did not return atlas geometry at ${width}px`)
  return JSON.parse(decodeURIComponent(encoded)) as LayoutResult
}

describe('system atlas rendered responsive geometry', () => {
  it.each([320, 375, 500, 768, 1024, 1025, 1280, 1440])(
    'contains every admitted node without overlap at %ipx',
    (width) => {
      const layout = renderAt(width)
      expect(layout.clientWidth).toBe(width)
      expect(layout.scrollWidth).toBe(width)
      expect(
        layout.contained,
        JSON.stringify({ map: layout.map, cards: layout.rectangles }),
      ).toBe(true)
      expect(layout.intersections, JSON.stringify(layout.rectangles)).toEqual([])
    },
    65_000,
  )

  it.each([320, 375])(
    'keeps the opened technical ledger inside a %ipx viewport',
    (width) => {
      const layout = renderAt(width, live, true)
      expect(layout.clientWidth).toBe(width)
      expect(layout.scrollWidth).toBe(width)
      expect(layout.contained).toBe(true)
      expect(layout.intersections).toEqual([])
    },
    65_000,
  )

  it.each([320, 375])(
    'keeps the no-runtime contract above the technical ledger at %ipx',
    (width) => {
      const layout = renderAt(width, null)
      expect(layout.clientWidth).toBe(width)
      expect(layout.scrollWidth).toBe(width)
      expect(layout.contained).toBe(true)
      expect(layout.emptyBeforeTechnical).toBe(true)
    },
    65_000,
  )

  it.each([1280, 1440])(
    'fits all 24 schema-admitted nodes without overlap at %ipx',
    (width) => {
      const layout = renderAt(width, maxSnapshot)
      expect(layout.clientWidth).toBe(width)
      expect(layout.scrollWidth).toBe(width)
      expect(layout.contained).toBe(true)
      expect(layout.intersections, JSON.stringify(layout.rectangles)).toEqual([])
    },
    65_000,
  )
})

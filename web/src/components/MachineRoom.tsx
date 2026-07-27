'use client'

/**
 * THE MACHINE ROOM — the running system, drawn while it runs.
 *
 * `web/` is a static export (`AGENTS.md`): there is no Next.js server at
 * runtime, so this fetches and polls `/api/v1/live` from the browser. What the
 * export writes to disk is the *map* — every part, its plain-English name, and
 * one line saying what it is — with every reading explicitly marked as absent.
 * That page is complete and honest with JavaScript switched off; turning
 * JavaScript on fills the readings in.
 *
 * Three things can change, and each is driven by an exact field in the current
 * feed:
 *
 *   the flowing lines   `links[].event_rate`     0 => the line is still
 *   the pulsing marks   `nodes[].activity_rate`  0 or not answering => still
 *   the age counter     `freshness_s` + elapsed wall-clock since the fetch
 *
 * Nothing else animates, and no motion runs on a number the feed did not
 * supply. The previous public contract supplies categorical bands instead of
 * these numbers; that entire report stays still, with every missing exact
 * reading labelled as such.
 *
 * The connections are drawn from *measured* card positions rather than from a
 * hand-written coordinate table, so the picture is correct at any width and
 * survives the grid reflowing from five columns to one.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from 'react'

import {
  ageSnapshot,
  machineView,
  normalizeLivePayload,
  type MachineReading,
  type MachineNodeView,
  type Measurement,
} from '@/lib/machineRoom'

/** The publisher pushes every 60s; three looks per push is plenty. */
const POLL_MS = 20_000

const TONE: Record<string, string> = {
  healthy: 'var(--color-sapphire)',
  degraded: 'var(--color-degraded)',
  down: 'var(--color-failed)',
  unknown: 'var(--color-ink-faint)',
}

export type WireBox = { x: number; y: number; w: number; h: number }

/**
 * A curve between two measured boxes, leaving and arriving on whichever pair of
 * edges faces the other box. Chooses a horizontal or a vertical run by which
 * distance dominates, which is what makes one code path work for the wide
 * five-column diagram and the single-column stack on a phone.
 */
export function wire(from: WireBox, to: WireBox): string {
  const a = { x: from.x + from.w / 2, y: from.y + from.h / 2 }
  const b = { x: to.x + to.w / 2, y: to.y + to.h / 2 }
  const dx = b.x - a.x
  const dy = b.y - a.y

  if (Math.abs(dx) >= Math.abs(dy)) {
    const start = dx > 0 ? from.x + from.w : from.x
    const end = dx > 0 ? to.x : to.x + to.w
    const bend = Math.max(22, Math.abs(end - start) * 0.5) * (dx > 0 ? 1 : -1)
    return `M ${start} ${a.y} C ${start + bend} ${a.y}, ${end - bend} ${b.y}, ${end} ${b.y}`
  }

  const start = dy > 0 ? from.y + from.h : from.y
  const end = dy > 0 ? to.y : to.y + to.h
  const bend = Math.max(22, Math.abs(end - start) * 0.5) * (dy > 0 ? 1 : -1)
  return `M ${a.x} ${start} C ${a.x} ${start + bend}, ${b.x} ${end - bend}, ${b.x} ${end}`
}

function Figure({ reading }: { reading: Measurement }) {
  if (!reading.measured) return <span className="mr-unmeasured">{reading.text}</span>
  return <b>{reading.text}</b>
}

export default function MachineRoom() {
  const [reading, setReading] = useState<MachineReading | null>(null)
  const [unreachable, setUnreachable] = useState(false)
  const [receivedAt, setReceivedAt] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [active, setActive] = useState<string | null>(null)
  const [boxes, setBoxes] = useState<Record<string, WireBox>>({})

  /* ---- the feed ---------------------------------------------------------- */

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const response = await fetch('/api/v1/live', {
          headers: { Accept: 'application/json' },
          cache: 'no-store',
        })
        if (!response.ok) throw new Error(String(response.status))
        const data = normalizeLivePayload(await response.json())
        if (data === null) throw new Error('unsupported live payload')
        if (cancelled) return
        setReading(data)
        setReceivedAt(Date.now())
        setElapsed(0)
        setUnreachable(false)
      } catch {
        // Keep the last real reading on screen; it ages, and the narration
        // says so. Replacing it with nothing would lose information, and
        // replacing it with a guess would be the thing this site argues against.
        if (!cancelled) setUnreachable(true)
      }
    }

    poll()
    const timer = setInterval(poll, POLL_MS)

    // A backgrounded tab should not keep polling, but it must not come back
    // showing a reading from before lunch either.
    const onVisible = () => {
      if (document.visibilityState === 'visible') poll()
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      cancelled = true
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  /* ---- real elapsed time since the reading arrived ----------------------- */

  useEffect(() => {
    if (receivedAt === null) return
    const tick = setInterval(() => setElapsed((Date.now() - receivedAt) / 1000), 1000)
    return () => clearInterval(tick)
  }, [receivedAt])

  const view = useMemo(
    () => machineView(
      reading ? ageSnapshot(reading.snapshot, elapsed) : null,
      { unreachable, precision: reading?.precision },
    ),
    [reading, elapsed, unreachable],
  )

  /* ---- where the browser actually put each card -------------------------- */

  const stage = useRef<HTMLDivElement>(null)
  const cards = useRef(new Map<string, HTMLElement>())
  const nodeKey = view.nodes.map((node) => node.id).join('|')

  const measure = useCallback(() => {
    const root = stage.current
    if (!root) return
    const base = root.getBoundingClientRect()
    const next: Record<string, WireBox> = {}
    cards.current.forEach((element, id) => {
      const rect = element.getBoundingClientRect()
      next[id] = {
        x: rect.left - base.left,
        y: rect.top - base.top,
        w: rect.width,
        h: rect.height,
      }
    })
    // Guarded so a ResizeObserver callback that changes nothing cannot loop.
    setBoxes((current) => (JSON.stringify(current) === JSON.stringify(next) ? current : next))
  }, [])

  useEffect(() => {
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    if (stage.current) observer.observe(stage.current)
    cards.current.forEach((element) => observer.observe(element))
    return () => observer.disconnect()
  }, [measure, nodeKey])

  /* ---- reading one part highlights only what it touches ------------------ */

  const neighbours = useMemo(() => {
    if (!active) return null
    const set = new Set<string>([active])
    for (const link of view.links) {
      if (link.source === active) set.add(link.target)
      if (link.target === active) set.add(link.source)
    }
    return set
  }, [active, view.links])

  const drawn = view.links
    .map((link) => ({ link, from: boxes[link.source], to: boxes[link.target] }))
    .filter((entry) => entry.from && entry.to)

  const tone = view.narration.tone

  return (
    <section
      className="mr"
      aria-labelledby="machine-room-heading"
      data-precision={view.precision ?? 'none'}
    >
      {/* ---- status line ---- */}
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <p className="flex items-center gap-2.5 font-mono text-[11px] tracking-[0.18em] uppercase">
            <span
              aria-hidden="true"
              className="inline-block h-1.5 w-1.5 shrink-0"
              style={{
                background:
                  view.mode === 'live'
                    ? 'var(--color-sapphire)'
                    : view.mode === 'unreachable'
                      ? 'var(--color-failed)'
                      : 'var(--color-degraded)',
              }}
            />
            <span
              style={{
                color:
                  view.mode === 'live'
                    ? 'var(--color-sapphire)'
                    : view.mode === 'unreachable'
                      ? 'var(--color-failed)'
                      : 'var(--color-degraded)',
              }}
            >
              {view.statusWord}
            </span>
            <span className="text-ink-faint">
              {view.age.measured ? `· reading taken ${view.age.text}` : '· no reading yet'}
            </span>
          </p>
          {view.hasReading && (
            <span
              className={`status-chip status-chip--${view.execution.tone === 'neutral' ? 'sapphire' : view.execution.tone}`}
            >
              <span className="status-chip__dot" aria-hidden="true" />
              Desk {view.execution.desk}
            </span>
          )}
        </div>
        <div className="text-right font-mono text-[11px] leading-relaxed text-ink-faint">
          <p>{view.detailNote}</p>
          <p>this page asks the system again every {POLL_MS / 1000} seconds</p>
        </div>
      </div>
      <p className="sr-only" aria-live="polite">
        {view.statusWord}. {view.detailNote}
      </p>

      {/* ---- the machine speaking for itself ---- */}
      <h2 id="machine-room-heading" className="sr-only">
        The system, right now
      </h2>
      {/* The one place on the site where the headline is written by the machine
          about itself. The opening sentence gets display size; the rest are the
          supporting detail and are set as such. Both come from the same call. */}
      <div
        className="mt-6 border-l-2 pl-5 md:pl-6"
        style={{
          borderLeftColor:
            tone === 'healthy'
              ? 'var(--color-sapphire)'
              : tone === 'degraded'
                ? 'var(--color-degraded)'
                : 'var(--color-ink-faint)',
        }}
      >
        <p className="mr-narration max-w-3xl">{view.narration.sentences[0]}</p>
        {view.narration.sentences.length > 1 && (
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-ink-dim text-pretty md:text-lg">
            {view.narration.sentences.slice(1).join(' ')}
          </p>
        )}
      </div>

      {!view.hasReading && (
        <p className="mt-5 max-w-2xl font-mono text-[11px] leading-relaxed text-ink-faint">
          {view.mode === 'unreachable'
            ? 'The system did not answer. What follows is the map of its parts, with no readings — nothing here is being guessed at.'
            : 'What follows is the map of the parts, with no readings yet. It fills in as soon as the system answers.'}
        </p>
      )}

      {/* ---- the diagram ---- */}
      <div ref={stage} className="mr-stage mt-10">
        <svg className="mr-wires" width="100%" height="100%" aria-hidden="true" focusable="false" data-ready={drawn.length > 0}>
          {drawn.map(({ link, from, to }) => {
            const path = wire(from, to)
            const lit = neighbours === null || (neighbours.has(link.source) && neighbours.has(link.target))
            const moving = link.flowSeconds !== null
            const rateKnown = link.rate.measured
            const colour =
              link.health === 'down'
                ? 'var(--color-failed)'
                : link.health === 'degraded'
                  ? 'var(--color-degraded)'
                  : link.health === 'healthy'
                    ? 'var(--color-sapphire)'
                    : 'var(--color-line-lit)'

            return (
              <g key={link.id} opacity={lit ? 1 : 0.16} style={{ transition: 'opacity .3s ease' }}>
                {/* The bed the connection sits in — always drawn, so a
                    connection that carries nothing is still visibly there. */}
                <path d={path} fill="none" stroke="var(--color-line)" strokeWidth={link.weight + 3} />
                {/* Glow, only where something measurable is actually moving. */}
                {moving && (
                  <path
                    d={path}
                    fill="none"
                    stroke={colour}
                    strokeWidth={link.weight + 5}
                    opacity={0.1}
                  />
                )}
                <path
                  d={path}
                  fill="none"
                  stroke={colour}
                  strokeWidth={link.weight}
                  strokeLinecap="round"
                  opacity={moving ? 0.95 : rateKnown ? 0.65 : 0.32}
                  strokeDasharray={moving ? '7 11' : rateKnown ? undefined : '2 7'}
                  className={moving ? 'flow' : undefined}
                  style={moving ? { animationDuration: `${link.flowSeconds}s` } : undefined}
                />
              </g>
            )
          })}
        </svg>

        <div className="mr-grid">
          {view.nodes.map((node) => (
            <NodeCard
              key={node.id}
              node={node}
              related={neighbours === null ? null : neighbours.has(node.id)}
              register={(element) => {
                if (element) cards.current.set(node.id, element)
                else cards.current.delete(node.id)
              }}
              onRead={() => setActive(node.id)}
              onRelease={() => setActive(null)}
            />
          ))}
        </div>
      </div>

      {/* ---- vitals ---- */}
      <dl className="mt-12 grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
        {view.vitals.map((vital) => (
          <div key={vital.label} className="bg-void px-5 py-5">
            <dt className="font-mono text-[10px] tracking-[0.16em] text-ink-faint uppercase">
              {vital.label}
            </dt>
            <dd className="tnum mt-3 font-display text-3xl leading-none font-semibold text-ink">
              {vital.value}
            </dd>
            <dd className="mt-3 text-[12px] leading-relaxed text-ink-dim">{vital.note}</dd>
          </div>
        ))}
      </dl>

      {/* ---- execution + money ---- */}
      <div className="mr-execution mt-8" data-tone={view.execution.tone}>
        <div className="mr-execution__strip" aria-label="Execution state">
          <div className={`mr-execution__chip mr-execution__chip--${view.execution.tone}`}>
            <span>Desk</span>
            <strong>{view.execution.desk}</strong>
          </div>
          <div className="mr-execution__chip">
            <span>Market rail</span>
            <strong>{view.execution.rail}</strong>
          </div>
          <div className="mr-execution__chip">
            <span>Approval</span>
            <strong>{view.execution.gate}</strong>
          </div>
        </div>
        <p className="mr-execution__money">
          <span className="font-mono text-[10px] tracking-[0.18em] text-ink-faint uppercase">
            Money
          </span>
          <span className="mt-2 block text-[15px] leading-relaxed text-ink-dim text-pretty">
            {view.money}
          </span>
        </p>
      </div>

      {/* ---- how to read it ---- */}
      <div className="mt-12 grid gap-x-10 gap-y-6 border-t border-line pt-8 sm:grid-cols-2 lg:grid-cols-4">
        {[
          {
            k: 'Moving lines',
            v: 'Motion appears only when the report supplies an exact rate above zero. Faster means a larger reported rate.',
          },
          {
            k: 'Solid still lines',
            v: 'The report supplied an exact zero. That is a reading: the connection exists and nothing is moving through it.',
          },
          {
            k: 'Dotted lines',
            v: 'No exact rate was supplied. A band such as “busy” is never converted into a plausible-looking number or motion.',
          },
          {
            k: 'The coloured marks',
            v: 'Sapphire answered when asked. Amber answered badly. Red stopped answering. Grey means nobody has asked yet.',
          },
        ].map((item) => (
          <div key={item.k}>
            <p className="font-mono text-[10px] tracking-[0.16em] text-ink-faint uppercase">
              {item.k}
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-dim">{item.v}</p>
          </div>
        ))}
      </div>

      {/* ---- the same thing, as text ---- */}
      <details className="mt-10 border border-line bg-raised/40">
        <summary className="cursor-pointer px-5 py-4 font-mono text-[11px] tracking-[0.16em] text-ink-dim uppercase hover:text-ink">
          Read all of this as text instead
        </summary>
        <div className="border-t border-line px-5 py-6">
          <p className="max-w-3xl text-sm leading-relaxed text-ink-dim">{view.narration.text}</p>

          <TextTable
            caption="Every part of the system"
            head={['Part', 'What it is', 'State', 'How busy', 'Heard from']}
            rows={view.nodes.map((node) => [
              node.plainName,
              node.oneLiner,
              node.healthWord,
              node.loadWord,
              node.age,
            ])}
          />

          <TextTable
            caption="Every connection between them"
            head={['Connection', 'What it is', 'State', 'How much is going through', 'Time to answer']}
            rows={view.links.map((link) => [
              link.plainName,
              link.oneLiner,
              link.health === null ? 'No reading' : link.health === 'healthy' ? 'Working' : link.health === 'degraded' ? 'Struggling' : 'Not answering',
              link.rate,
              link.latency,
            ])}
          />

          <p className="mt-8 text-[13px] leading-relaxed text-ink-faint">
            &ldquo;Not measured&rdquo; is not a rendering failure. It means this report supplied
            no exact figure for that field. A missing value and a measured zero are different
            claims, and this page keeps them different.
          </p>
        </div>
      </details>

      <details className="mt-3 border border-line bg-raised/40">
        <summary className="cursor-pointer px-5 py-3 font-mono text-[11px] tracking-[0.16em] text-ink-dim uppercase hover:text-ink">
          Reproduce every live reading
        </summary>
        <div className="border-t border-line px-5 py-4">
          <p className="max-w-3xl text-[13px] leading-relaxed text-ink-dim">
            This page polls{' '}
            <code className="font-mono text-ink">/api/v1/live</code> on the same origin.
            Fetch the canonical public endpoint to inspect the exact JSON behind every
            figure:
          </p>
          <pre className="mt-3 overflow-x-auto border border-line bg-void px-4 py-3 font-mono text-[11px] text-sapphire">
            <code>curl -s https://sapphirealpha.xyz/api/v1/live | jq .</code>
          </pre>
        </div>
      </details>

      {view.unnamed.length > 0 && (
        <p className="mt-8 border border-degraded/40 px-4 py-3 font-mono text-[11px] leading-relaxed text-degraded">
          {view.unnamed.length} part{view.unnamed.length === 1 ? '' : 's'} of the system
          reached this page without a plain-English name. That is a defect on our side, not
          something you need to decode.
        </p>
      )}
    </section>
  )
}

/* -------------------------------------------------------------------------- */

function NodeCard({
  node,
  related,
  register,
  onRead,
  onRelease,
}: {
  node: MachineNodeView
  related: boolean | null
  register: (element: HTMLElement | null) => void
  onRead: () => void
  onRelease: () => void
}) {
  const colour = TONE[node.health ?? 'unknown'] ?? TONE.unknown

  return (
    <article
      ref={register}
      className="mr-node"
      data-related={related === null ? undefined : String(related)}
      style={{ '--col': node.col, '--row': node.row, '--mr-tone': colour } as CSSProperties}
      onMouseEnter={onRead}
      onMouseLeave={onRelease}
    >
      <p className="mr-node__state">
        <span
          className="mr-node__dot"
          data-breathing={node.pulseSeconds !== null}
          style={
            node.pulseSeconds !== null
              ? { animationDuration: `${node.pulseSeconds}s` }
              : undefined
          }
          aria-hidden="true"
        />
        {node.healthWord}
        {node.ownReadingStale && <span className="text-ink-faint"> · old reading</span>}
      </p>

      <h3 className="mr-node__name">{node.plainName}</h3>
      <p className="mr-node__what">{node.oneLiner}</p>

      <div
        className="mr-node__meter"
        role="img"
        aria-label={`How busy: ${node.loadWord.toLowerCase()}`}
      >
        {[1, 2, 3, 4].map((step) => (
          <span key={step} data-on={step <= node.loadSteps} />
        ))}
      </div>

      <p className="mr-node__foot">
        <span>{node.loadWord}</span>
        <span>
          <Figure reading={node.activity} />
        </span>
        <span>
          heard from <Figure reading={node.age} />
        </span>
      </p>
    </article>
  )
}

function TextTable({
  caption,
  head,
  rows,
}: {
  caption: string
  head: string[]
  rows: (string | Measurement)[][]
}) {
  return (
    <div className="mt-8 overflow-x-auto">
      <table className="w-full border-collapse text-left text-[13px]">
        <caption className="mb-3 text-left font-mono text-[10px] tracking-[0.16em] text-ink-faint uppercase">
          {caption}
        </caption>
        <thead>
          <tr>
            {head.map((cell) => (
              <th
                key={cell}
                scope="col"
                className="border-b border-line-lit py-2 pr-5 font-mono text-[10px] font-medium tracking-[0.12em] text-ink-faint uppercase"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, column) => (
                <td
                  key={column}
                  className={`border-b border-line py-2.5 pr-5 align-top leading-relaxed ${
                    column === 0 ? 'text-ink' : 'text-ink-dim'
                  }`}
                >
                  {typeof cell === 'string' ? cell : <Figure reading={cell} />}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

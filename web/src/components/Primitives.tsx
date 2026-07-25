import type { ReactNode } from 'react'

/**
 * The one green thing on the site. Because `Verified` is the sole owner of the
 * verified colour token, a green pixel anywhere on the page carries meaning
 * rather than decoration — which is the whole reason the palette reserves it.
 */
export function Verified({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[11px] tracking-[0.12em] text-verified uppercase">
      <span className="pulse-verified inline-block h-1.5 w-1.5 shrink-0 bg-verified" aria-hidden="true" />
      {children}
    </span>
  )
}

/** Small mono label used above every section and stat. */
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="font-mono text-[11px] tracking-[0.2em] text-sapphire uppercase">{children}</p>
  )
}

export function Rule() {
  return <div className="rule my-16" aria-hidden="true" />
}

/** Page-level header shared by all five interior pages. */
export function PageHeader({
  eyebrow,
  title,
  lede,
}: {
  eyebrow: string
  title: string
  lede: string
}) {
  return (
    <header className="mx-auto max-w-6xl px-6 pt-20 pb-4 md:pt-28">
      <div className="rise">
        <Eyebrow>{eyebrow}</Eyebrow>
      </div>
      <h1
        className="rise mt-5 max-w-4xl font-display text-5xl leading-[0.95] font-semibold tracking-[-0.03em] text-balance md:text-7xl"
        style={{ animationDelay: '80ms' }}
      >
        {title}
      </h1>
      <p
        className="rise mt-7 max-w-2xl text-lg leading-relaxed text-ink-dim text-pretty"
        style={{ animationDelay: '160ms' }}
      >
        {lede}
      </p>
    </header>
  )
}

/** Bordered content block. Hairlines only — no shadow, no glass, no radius. */
export function Panel({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={`border border-line bg-raised/60 p-6 md:p-8 ${className}`}>{children}</div>
  )
}

/**
 * Terminal block. Used for anything the reader could paste into a shell —
 * commands, endpoint transcripts, config. `$` prefixes are rendered rather than
 * written into the string so the content stays copy-pasteable.
 */
export function Terminal({
  title,
  lines,
  scanline = false,
}: {
  title: string
  lines: { prompt?: boolean; text: string; tone?: 'ink' | 'dim' | 'verified' | 'sapphire' }[]
  scanline?: boolean
}) {
  const tones = {
    ink: 'text-ink',
    dim: 'text-ink-faint',
    verified: 'text-verified',
    sapphire: 'text-sapphire',
  } as const

  return (
    <div className="relative overflow-hidden border border-line bg-sunk">
      {scanline && (
        <div
          aria-hidden="true"
          className="sweep pointer-events-none absolute inset-x-0 top-0 z-10 h-8 bg-gradient-to-b from-transparent via-sapphire/6 to-transparent"
        />
      )}

      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <p className="font-mono text-[11px] tracking-[0.14em] text-ink-faint uppercase">{title}</p>
        <div className="flex gap-1.5" aria-hidden="true">
          <span className="h-1.5 w-1.5 bg-line-lit" />
          <span className="h-1.5 w-1.5 bg-line-lit" />
          <span className="h-1.5 w-1.5 bg-sapphire/50" />
        </div>
      </div>

      <pre className="overflow-x-auto px-4 py-4 font-mono text-[12px] leading-[1.85] md:text-[13px]">
        <code>
          {lines.map((line, i) => (
            <span key={i} className={`block ${tones[line.tone ?? 'ink']}`}>
              {line.prompt && <span className="mr-2 text-sapphire select-none">$</span>}
              {/* An empty <span> has no line box, so blank spacer lines would
                  collapse. A non-breaking space preserves the rhythm. */}
              {line.text === '' ? ' ' : line.text}
            </span>
          ))}
        </code>
      </pre>
    </div>
  )
}

/** Definition row used across Architecture / Security / On-Chain. */
export function Row({
  term,
  children,
  status,
}: {
  term: string
  children: ReactNode
  status?: ReactNode
}) {
  return (
    <div className="grid gap-2 border-b border-line py-5 md:grid-cols-[220px_1fr_auto] md:items-baseline md:gap-6">
      <dt className="font-mono text-[12px] tracking-[0.1em] text-ink uppercase">{term}</dt>
      <dd className="text-sm leading-relaxed text-ink-dim">{children}</dd>
      {status && <div className="md:justify-self-end">{status}</div>}
    </div>
  )
}

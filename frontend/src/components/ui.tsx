import type { ReactNode } from 'react'

/* Desk primitives, matching web/src/components/Primitives.tsx. Both surfaces
   draw from ../../shared/theme.css, so these stay visually identical to the
   marketing site by construction rather than by resemblance. */

export type Tone = 'verified' | 'degraded' | 'failed' | 'neutral' | 'sapphire'

/**
 * Map a telemetry status string onto the palette.
 *
 * The house rule that green means verified is enforced here: ordinary runtime
 * health and activity resolve to sapphire, while only an explicit verification
 * resolves to `verified`. Anything unrecognised falls through to neutral rather
 * than optimistically reading as green.
 */
export function toneFor(status: string | null | undefined): Tone {
  switch ((status ?? '').toLowerCase()) {
    case 'live':
    case 'healthy':
    case 'ok':
    case 'recovered':
    case 'working':
      return 'sapphire'
    case 'verified':
      return 'verified'
    case 'warming':
    case 'stale':
    case 'degraded':
    case 'pending':
    case 'blocked':
    case 'verifying':
      return 'degraded'
    case 'offline':
    case 'down':
    case 'failed':
      return 'failed'
    default:
      return 'neutral'
  }
}

const TEXT: Record<Tone, string> = {
  verified: 'text-verified',
  degraded: 'text-degraded',
  failed: 'text-failed',
  sapphire: 'text-sapphire',
  neutral: 'text-ink-dim',
}

const BG: Record<Tone, string> = {
  verified: 'bg-verified',
  degraded: 'bg-degraded',
  failed: 'bg-failed',
  sapphire: 'bg-sapphire',
  neutral: 'bg-ink-faint',
}

export function toneText(tone: Tone) {
  return TEXT[tone]
}

/** Square status dot. Pulses only while genuinely live. */
export function Dot({ tone, pulse = false }: { tone: Tone; pulse?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block h-1.5 w-1.5 shrink-0 ${BG[tone]} ${pulse ? 'pulse-verified' : ''}`}
    />
  )
}

/** Status pill: dot + label, coloured by tone. */
export function StatusPill({
  status,
  label,
  pulse,
}: {
  status: string | null | undefined
  label?: string
  pulse?: boolean
}) {
  const tone = toneFor(status)
  return (
    <span
      className={`inline-flex items-center gap-2 border border-line px-2.5 py-1 font-mono text-[11px] tracking-[0.12em] uppercase ${TEXT[tone]}`}
    >
      <Dot tone={tone} pulse={pulse ?? tone === 'verified'} />
      {label ?? status ?? 'offline'}
    </span>
  )
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="font-mono text-[11px] tracking-[0.2em] text-sapphire uppercase">{children}</p>
}

/** Bordered content block. Hairlines only — no shadow, glass, or radius. */
export function Panel({
  children,
  className = '',
  id,
  label,
}: {
  children: ReactNode
  className?: string
  id?: string
  label?: string
}) {
  return (
    <section
      id={id}
      aria-label={label}
      className={`min-w-0 border border-line bg-raised/60 ${className}`}
    >
      {children}
    </section>
  )
}

export function PanelHeading({
  eyebrow,
  title,
  note,
  right,
}: {
  eyebrow: string
  title: string
  note?: string
  right?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line px-6 py-5">
      <div>
        <Eyebrow>{eyebrow}</Eyebrow>
        <h2 className="mt-2 font-display text-xl font-semibold tracking-[-0.015em] text-ink">
          {title}
        </h2>
        {note && <p className="mt-1.5 text-sm text-ink-faint">{note}</p>}
      </div>
      {right}
    </div>
  )
}

/**
 * Label + value. `value` is deliberately a string everywhere — telemetry that is
 * missing must render as "not observed" rather than as a fabricated zero.
 */
export function Metric({
  label,
  value,
  tone = 'neutral',
}: {
  label: string
  value: string
  tone?: Tone
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="font-mono text-[11px] tracking-[0.14em] text-ink-faint uppercase">
        {label}
      </span>
      <strong
        className={`tnum font-display text-xl leading-none font-semibold ${
          tone === 'neutral' ? 'text-ink' : TEXT[tone]
        }`}
      >
        {value}
      </strong>
    </div>
  )
}

export function Empty({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2.5 border border-dashed border-line px-4 py-5 font-mono text-[12px] text-ink-faint">
      <Dot tone="neutral" />
      {label}
    </div>
  )
}

export function Count({ children }: { children: ReactNode }) {
  return (
    <span className="tnum border border-line-lit px-2.5 py-1 font-mono text-[12px] text-ink-dim">
      {children}
    </span>
  )
}

/** Inline notice strip. Never green — a notice is never a verified state. */
export function Notice({ tone, children }: { tone: 'degraded' | 'failed'; children: ReactNode }) {
  const border = tone === 'failed' ? 'border-failed' : 'border-degraded'
  return (
    <div className={`border-l-2 ${border} bg-raised/60 px-4 py-3 text-sm text-ink-dim`}>
      {children}
    </div>
  )
}

/**
 * Rendering a number honestly.
 *
 * The whole point of deleting the redaction tier was that a real figure which
 * jitters reads as alive where an adjective reads as a brochure. The failure
 * mode on the other side is worse: a *fabricated* figure reads as alive too,
 * and is a lie. So every formatter here takes `number | null | undefined` and
 * turns absence into words, never into a zero and never into a placeholder.
 *
 * `links[].latency_ms` is `null` for every link in production right now — no
 * link probes are configured — so the not-measured path is the common path, not
 * an edge case. It has to be correct.
 *
 * Zero is not absence. A link carrying no events reports `event_rate: 0`, and
 * that is a measurement: it renders as `0/min`, not as "not measured".
 */

/** What the desk says when a field exists in the schema but nothing measured it. */
export const NOT_MEASURED = 'not measured'

/** What the desk says when there is no observation at all to age. */
export const NOT_OBSERVED = 'not observed'

function absent(value: number | null | undefined): boolean {
  return value === null || value === undefined || Number.isNaN(value)
}

/**
 * Round-trip time. `null` today for every link; when a probe starts reporting,
 * this lights up on its own with no further change here.
 */
export function formatLatency(ms: number | null | undefined): string {
  if (absent(ms)) return NOT_MEASURED
  const value = ms as number
  if (value < 10) return `${Math.round(value * 10) / 10} ms`
  return `${Math.round(value)} ms`
}

/** Events per minute. */
export function formatRate(perMin: number | null | undefined): string {
  if (absent(perMin)) return NOT_MEASURED
  const value = perMin as number
  if (value > 0 && value < 1) return '<1/min'
  return `${Math.round(value)}/min`
}

/** Age of an observation, in words. */
export function formatAge(seconds: number | null | undefined): string {
  if (absent(seconds)) return NOT_OBSERVED
  const value = Math.max(0, seconds as number)
  if (value < 60) return `${Math.round(value)}s ago`
  const minutes = Math.round(value / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(value / 3600)
  /* Once an observation is inside its final hour before a full day, "1d" is
     more truthful than displaying a rounded-down "23h". Use ceil only for the
     boundary; the displayed count stays nearest-unit rounded. */
  if (Math.ceil(value / 3600) < 24) return `${hours}h ago`
  return `${Math.round(value / 86400)}d ago`
}

/** A whole number that might not exist. Never renders a missing count as 0. */
export function formatCount(value: number | null | undefined): string {
  if (absent(value)) return NOT_OBSERVED
  return String(Math.round(value as number))
}

export function formatClockTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return '—'
  return at.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export interface FlowProfile {
  /** True only when the edge is actually carrying events. */
  moving: boolean
  /** Stroke width in user units. */
  strokeWidth: number
  /** Seconds per dash cycle. `0` means the renderer must not animate at all. */
  durationS: number
}

const MIN_STROKE = 1.2
const MAX_STROKE = 5
const FASTEST_S = 2.2
const SLOWEST_S = 12

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value))
}

/**
 * Turn a measured event rate into the only motion on the loom.
 *
 * A link that reports no rate, or a rate of zero, gets `moving: false` and a
 * duration of exactly `0`, and the renderer draws it still. Nothing on this
 * page may animate to suggest activity the snapshot does not report — an
 * idling shimmer on a dead edge is the same lie as printing a made-up latency.
 */
export function flowProfile(eventRate: number | null | undefined): FlowProfile {
  if (absent(eventRate) || (eventRate as number) <= 0) {
    return { moving: false, strokeWidth: MIN_STROKE, durationS: 0 }
  }
  const rate = eventRate as number
  return {
    moving: true,
    strokeWidth: clamp(MIN_STROKE + Math.log10(1 + rate) * 1.4, MIN_STROKE, MAX_STROKE),
    /* Faster edges cycle faster. Clamped at both ends so a 600/min edge stays
       watchable and an 8/min edge still visibly moves. */
    durationS: Math.round(clamp((60 / rate) * 2, FASTEST_S, SLOWEST_S) * 10) / 10,
  }
}

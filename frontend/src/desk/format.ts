/**
 * Rendering a number honestly.
 *
 * The whole point of deleting the redaction tier was that a real figure which
 * jitters reads as alive where an adjective reads as a brochure. The failure
 * mode on the other side is worse: a *fabricated* figure reads as alive too,
 * and is a lie. So every formatter here takes `number | null | undefined` and
 * turns absence into words, never into a zero and never into a placeholder.
 *
 * Zero is not absence. A measured count of zero stays zero.
 */

/** What the desk says when there is no observation at all to age. */
export const NOT_OBSERVED = 'not observed'

function absent(value: number | null | undefined): boolean {
  return value === null || value === undefined || Number.isNaN(value)
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

/** Full UTC observation stamp. A clock without its date or zone is ambiguous. */
export function formatObservedAt(iso: string | null | undefined): string {
  if (!iso) return NOT_OBSERVED
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return NOT_OBSERVED
  return at.toISOString().replace('T', ' ').replace('.000Z', 'Z')
}

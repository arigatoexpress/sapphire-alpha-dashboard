import type { LiveSnapshot } from '@shared/telemetry'
import fixture from '../../../shared/__tests__/fixtures/live-snapshot.json'

/**
 * The captured snapshot the shared modules are pinned against.
 *
 * The desk's tests read the same file rather than inventing their own topology,
 * so a test cannot pass against a shape the backend never serves. It is the
 * real thing: eleven nodes over six zones, three of them sharing `compute`, and
 * nine links whose `latency_ms` is `null` on every one.
 */
export function liveSnapshot(): LiveSnapshot {
  /* Return a fresh value so a test that edits a nested reading cannot leak into
     the next test. `resolveJsonModule` keeps this fixture build-compatible; the
     previous node:fs read made the production TypeScript build depend on Node
     types that this browser package intentionally does not install. */
  return structuredClone(fixture) as LiveSnapshot
}

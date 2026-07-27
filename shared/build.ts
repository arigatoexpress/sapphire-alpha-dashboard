/** Runtime contract shared by the public site and operator observatory. */

export interface BuildSurfaceIdentity {
  entrypoint_url: string
  entrypoint_sha256: string | null
  asset_count: number
  manifest_sha256: string | null
}

export interface BuildIdentity {
  schema: 1
  source_sha: string
  build_id: string
  runtime_service: string
  runtime_revision: string
  surfaces: {
    operator: BuildSurfaceIdentity
    public: BuildSurfaceIdentity
  }
  complete: boolean
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function digest(value: unknown): value is string | null {
  return value === null || (typeof value === 'string' && /^[0-9a-f]{64}$/.test(value))
}

function label(value: unknown, fallback: string) {
  return (
    typeof value === 'string' &&
    value.length <= 128 &&
    (value === fallback || /^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(value))
  )
}

function surface(value: unknown): value is BuildSurfaceIdentity {
  return (
    record(value) &&
    typeof value.entrypoint_url === 'string' &&
    digest(value.entrypoint_sha256) &&
    Number.isInteger(value.asset_count) &&
    Number(value.asset_count) >= 0 &&
    Number(value.asset_count) <= 100_000 &&
    digest(value.manifest_sha256)
  )
}

export function parseBuildIdentity(value: unknown): BuildIdentity | null {
  if (
    !record(value) ||
    value.schema !== 1 ||
    !(
      value.source_sha === 'unknown' ||
      (typeof value.source_sha === 'string' && /^[0-9a-f]{40}([0-9a-f]{24})?$/.test(value.source_sha))
    ) ||
    !label(value.build_id, 'unknown') ||
    !label(value.runtime_service, 'local') ||
    !label(value.runtime_revision, 'local') ||
    typeof value.complete !== 'boolean' ||
    !record(value.surfaces) ||
    !surface(value.surfaces.operator) ||
    !surface(value.surfaces.public) ||
    value.surfaces.operator.entrypoint_url !== '/dashboard' ||
    value.surfaces.public.entrypoint_url !== '/'
  ) {
    return null
  }
  if (
    value.complete &&
    (value.source_sha === 'unknown' ||
      value.build_id === 'unknown' ||
      value.runtime_revision === 'local' ||
      value.surfaces.operator.asset_count === 0 ||
      value.surfaces.public.asset_count === 0 ||
      value.surfaces.operator.entrypoint_sha256 === null ||
      value.surfaces.public.entrypoint_sha256 === null ||
      value.surfaces.operator.manifest_sha256 === null ||
      value.surfaces.public.manifest_sha256 === null)
  ) {
    return null
  }
  return value as unknown as BuildIdentity
}

export function shortBuildValue(value: string | null, length = 12) {
  return value ? value.slice(0, length) : 'not observed'
}

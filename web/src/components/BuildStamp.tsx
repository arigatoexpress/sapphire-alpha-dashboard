'use client'

import { useEffect, useState } from 'react'
import { parseBuildIdentity, shortBuildValue } from '@shared/build'
import type { BuildIdentity } from '@shared/build'

export default function BuildStamp() {
  const [build, setBuild] = useState<BuildIdentity | null>(null)

  useEffect(() => {
    let active = true
    fetch('/api/build', { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<unknown>
      })
      .then((payload) => {
        if (active) setBuild(parseBuildIdentity(payload))
      })
      .catch(() => {
        if (active) setBuild(null)
      })
    return () => {
      active = false
    }
  }, [])

  if (!build) {
    return (
      <p className="mt-4 font-mono text-[11px] text-ink-faint">
        Runtime build not verified.{' '}
        <a className="text-ice underline-offset-4 hover:underline" href="/api/build">
          Inspect manifest
        </a>
      </p>
    )
  }

  return <BuildStampRecord build={build} />
}

export function BuildStampRecord({ build }: { build: BuildIdentity }) {
  const assets = build.surfaces.operator.asset_count + build.surfaces.public.asset_count
  return (
    <dl className="mt-4 space-y-2.5 font-mono text-[12px]">
      <div className="flex justify-between gap-4">
        <dt className="text-ink-faint">source</dt>
        <dd className="tnum text-ink-dim">{shortBuildValue(build.source_sha)}</dd>
      </div>
      <div className="flex justify-between gap-4">
        <dt className="text-ink-faint">build</dt>
        <dd className="tnum max-w-40 truncate text-ink-dim">{build.build_id}</dd>
      </div>
      <div className="flex justify-between gap-4">
        <dt className="text-ink-faint">revision</dt>
        <dd className="tnum max-w-40 truncate text-ink-dim">{build.runtime_revision}</dd>
      </div>
      <div className="flex justify-between gap-4">
        <dt className="text-ink-faint">assets</dt>
        <dd className="tnum text-ink-dim">{assets}</dd>
      </div>
      <div className="flex justify-between gap-4">
        <dt className="text-ink-faint">manifests</dt>
        <dd className="tnum text-ink-dim">
          {shortBuildValue(build.surfaces.operator.manifest_sha256, 8)}/
          {shortBuildValue(build.surfaces.public.manifest_sha256, 8)}
        </dd>
      </div>
      <div className="flex justify-between gap-4">
        <dt className="text-ink-faint">status</dt>
        <dd className={build.complete ? 'text-ice' : 'text-degraded'}>
          {build.complete ? 'attributed' : 'incomplete'}
        </dd>
      </div>
      <div className="flex justify-between gap-4">
        <dt className="text-ink-faint">record</dt>
        <dd>
          <a
            href="/api/build"
            className="underline-grow text-ice transition-colors hover:text-ink"
          >
            inspect JSON
          </a>
        </dd>
      </div>
    </dl>
  )
}

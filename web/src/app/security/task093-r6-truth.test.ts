import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('Task 093 R6 public security truth', () => {
  it('does not claim signature verification happens before parsing when parsing happens first', () => {
    const securityPage = readFileSync(
      resolve(process.cwd(), 'src/app/security/page.tsx'),
      'utf8',
    )
    const backend = readFileSync(resolve(process.cwd(), '../backend/main.py'), 'utf8')
    const endpoint = backend.slice(
      backend.indexOf('async def ingest_live_telemetry'),
      backend.indexOf('@app.get("/api/v1/live")'),
    )

    const copyClaimsVerifyBeforeParse = securityPage.includes(
      'mis-signed bodies are rejected before parsing',
    )
    const implementationParsesBeforeSignature =
      endpoint.indexOf('_decode_bounded_json') < endpoint.indexOf('live_telemetry_store.accept')

    expect(copyClaimsVerifyBeforeParse && implementationParsesBeforeSignature).toBe(false)
  })
})

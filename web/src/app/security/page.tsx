import type { Metadata } from 'next'
import { Eyebrow, PageHeader, Panel, Row, Rule, Terminal, Verified } from '@/components/Primitives'

export const metadata: Metadata = {
  title: 'Security',
  description:
    'Whitelisted public projections, HMAC-signed ingest, replay rejection, and key material ' +
    'that never enters a process. The Sapphire Alpha security model.',
  alternates: { canonical: '/security/' },
}

const CONTROLS = [
  {
    term: 'Default deny',
    body:
      'The public projection is a whitelist. A field is invisible to anonymous callers ' +
      'unless it was explicitly listed — so a new field added upstream leaks nothing until ' +
      'someone decides it should.',
  },
  {
    term: 'Signed ingest',
    body:
      'Telemetry is HMAC-signed by the collector and verified at the edge. Unsigned or ' +
      'mis-signed bodies are rejected before parsing, and replayed sequences are refused.',
  },
  {
    term: 'Address masking',
    body:
      'Wallet addresses are reduced to 0xabcd…1234 before serialization. No wallet ' +
      'identifier is exposed anonymously, not even a masked one.',
  },
  {
    term: 'PII stripping',
    body:
      'Chat ids, usernames, and anything matching a secret-like key are dropped from ' +
      'proposals and decisions before they reach a response body.',
  },
  {
    term: 'Key custody',
    body:
      'Private keys and seed phrases never enter a model context, a log, a repository, or ' +
      'a config file. They stay in OS-level custody and are used only through provisioned paths.',
  },
  {
    term: 'Transport',
    body:
      'Machines reach each other over a private mesh, not the open internet. The public ' +
      'edge is the single reachable surface and holds no inbound path to either host.',
  },
]

export default function Security() {
  return (
    <>
      <PageHeader
        eyebrow="Security"
        title="The public view is a whitelist, not a filter."
        lede="A filter removes what you remembered to remove. A whitelist shows only what you deliberately allowed — so the failure mode of forgetting is silence rather than disclosure."
      />

      <section className="mx-auto max-w-6xl px-6 pt-14">
        <div className="grid gap-12 lg:grid-cols-[0.95fr_1.05fr] lg:gap-16">
          <div>
            <Eyebrow>Threat posture</Eyebrow>
            <h2 className="mt-4 font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-4xl">
              Assume the edge is hostile.
            </h2>
            <div className="mt-7 space-y-5 text-base leading-relaxed text-ink-dim">
              <p>
                The Cloud Run service is treated as compromised-in-principle. It receives
                pushed telemetry and serves projections; it cannot reach into either host,
                hold execution keys, or originate a trade.
              </p>
              <p>
                Snapshot files are equally untrusted. Anything read from disk is passed
                through a whitelist that coerces types and drops path-like values, so a
                poisoned file cannot introduce fields the API never intended to serve.
              </p>
            </div>
          </div>

          <Terminal
            title="anonymous request — public projection"
            lines={[
              { prompt: true, text: 'curl -s https://sapphirealpha.xyz/api/v1/status' },
              { text: '{', tone: 'dim' },
              { text: '  "public_view": true,', tone: 'sapphire' },
              { text: '  "gate": {' },
              { text: '    "state": "disarmed",' },
              { text: '    "executor_alive": true' },
              { text: '  },' },
              { text: '  "system_health": { "dashboard": "ok" }' },
              { text: '}', tone: 'dim' },
              { text: '' },
              { text: '# absent by design:', tone: 'dim' },
              { text: '#   wallet address, exact balances, caps,', tone: 'dim' },
              { text: '#   proposal bodies, file paths, hostnames.', tone: 'dim' },
            ]}
          />
        </div>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6" aria-labelledby="controls-heading">
        <Eyebrow>Controls</Eyebrow>
        <h2
          id="controls-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance md:text-5xl"
        >
          Six properties, each under test.
        </h2>
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-ink-dim">
          Each of these is asserted by the suite rather than documented and hoped for. A
          regression that leaks a masked address or widens the public payload fails CI.
        </p>
        <dl className="mt-12 border-t border-line">
          {CONTROLS.map((control) => (
            <Row key={control.term} term={control.term} status={<Verified>under test</Verified>}>
              {control.body}
            </Row>
          ))}
        </dl>
      </section>

      <Rule />

      <section className="mx-auto max-w-6xl px-6">
        <div className="grid gap-8 md:grid-cols-2">
          <Panel>
            <Eyebrow>Hardening</Eyebrow>
            <ul className="mt-6 space-y-3.5 text-sm leading-relaxed text-ink-dim">
              <li>Path traversal rejected at middleware, before routing.</li>
              <li>Rate limits tighten automatically while public read is enabled.</li>
              <li>CORS defaults to deny; a single origin may be allowed explicitly.</li>
              <li>
                <span className="font-mono text-[12px]">nosniff</span>,{' '}
                <span className="font-mono text-[12px]">DENY</span> framing, and a strict
                referrer policy on every response.
              </li>
              <li>Constant-time credential comparison on the operator path.</li>
            </ul>
          </Panel>

          <Panel>
            <Eyebrow>Disclosure</Eyebrow>
            <p className="mt-6 text-sm leading-relaxed text-ink-dim">
              If you find a vulnerability in anything described here, report it before
              publishing. Reports are read the same day, and there is no legal threat waiting
              on the other end of one.
            </p>
            <p className="mt-5 text-sm leading-relaxed text-ink-dim">
              The security model above is a description of intent and current implementation.
              It is not a warranty, and no system is exhaustively secure.
            </p>
          </Panel>
        </div>
      </section>
    </>
  )
}

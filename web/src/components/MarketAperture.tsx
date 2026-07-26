import Link from 'next/link'
import { PUBLIC_DOCTRINE } from '@shared/doctrine'

export default function MarketAperture() {
  const { headline, posture, primary, lenses, inputCap, evidenceMinimum } =
    PUBLIC_DOCTRINE

  return (
    <section
      data-market-aperture="true"
      aria-labelledby="aperture-title"
      className="market-aperture rise"
    >
      <div className="aperture-copy">
        <p className="aperture-kicker">Sapphire Alpha · sovereign intelligence</p>
        <h1 id="aperture-title">{headline}</h1>
        <p className="aperture-lede">
          The mandate sets conviction. Independent research can challenge it,
          but no outside input can quietly become it.
        </p>

        <div className="aperture-contract">
          <div>
            <span>Current posture</span>
            <strong>{posture}</strong>
          </div>
          <div>
            <span>Primary cycle lens</span>
            <strong>{primary.name} · {primary.scope}</strong>
          </div>
        </div>

        <div className="aperture-actions">
          <Link href="/dashboard">Enter the live desk</Link>
          <Link href="/research/">Read the evidence →</Link>
        </div>
      </div>

      <div className="aperture-visual" aria-label="Research authority map">
        <div className="optic" aria-hidden="true">
          <div className="optic-halo" />
          <div className="optic-ring optic-ring-outer" />
          <div className="optic-ring optic-ring-primary" />
          <div className="optic-crosshair" />
          <div className="optic-core">
            <span>Mandate</span>
            <strong>Private</strong>
            <small>sets conviction</small>
          </div>
        </div>

        <div className="optic-primary">
          <span>Primary cycle</span>
          <strong>{primary.name}</strong>
        </div>

        <div className="optic-advisers">
          {lenses.map((lens) => (
            <div key={lens.name}>
              <strong>{lens.name}</strong>
              <span>{lens.scope}</span>
            </div>
          ))}
        </div>

        <p className="optic-boundary">Execution stays outside this lens</p>
      </div>

      <div className="aperture-telemetry aperture-telemetry-static" aria-label="Research safeguards">
        <div>
          <span>Authority</span>
          <strong>Private mandate</strong>
        </div>
        <div>
          <span>Independent checks</span>
          <strong>{evidenceMinimum}</strong>
        </div>
        <div>
          <span>Input cap</span>
          <strong>{inputCap}</strong>
        </div>
        <div>
          <span>Research role</span>
          <strong>Evidence, not authority</strong>
        </div>
      </div>
    </section>
  )
}

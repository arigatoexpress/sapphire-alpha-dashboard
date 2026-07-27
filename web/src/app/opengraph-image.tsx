import { ImageResponse } from 'next/og'
import { CORE_METRICS, MEASURED_SHA } from '@/data/metrics'

export const alt = 'Sapphire Alpha — verifiable autonomous infrastructure'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

/* Metadata image routes compile to Route Handlers, so `output: export` requires
   an explicit static opt-in. Without this the build fails rather than silently
   shipping a route the static host cannot serve. */
export const dynamic = 'force-static'

/* Rendered once at build time and written into `out/` as a static PNG, so the
   exported site has no runtime image dependency. Uses system-default fonts
   rather than fetching webfonts — a build-time network fetch here would make
   the deploy fail for a decorative reason. */
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          background: '#04070D',
          padding: 72,
          // Single sapphire light source, matching the site.
          backgroundImage:
            'radial-gradient(ellipse 80% 60% at 50% -10%, rgba(61,120,255,0.22), transparent 70%)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div
            style={{
              width: 26,
              height: 26,
              border: '2px solid #3D78FF',
              transform: 'rotate(45deg)',
              display: 'flex',
            }}
          />
          <div
            style={{
              display: 'flex',
              fontSize: 24,
              letterSpacing: 6,
              color: '#8A97AB',
              textTransform: 'uppercase',
            }}
          >
            Sapphire Alpha
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div
            style={{
              display: 'flex',
              fontSize: 116,
              fontWeight: 700,
              color: '#E6EDF7',
              letterSpacing: -4,
              lineHeight: 1,
            }}
          >
            Verify, don&rsquo;t trust.
          </div>
          <div
            style={{
              display: 'flex',
              marginTop: 28,
              fontSize: 30,
              color: '#8A97AB',
              maxWidth: 900,
              lineHeight: 1.4,
            }}
          >
            Market research and bounded agent infrastructure. Every figure ships with the command
            that reproduces it.
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-end',
            borderTop: '1px solid #1E2D4A',
            paddingTop: 28,
          }}
        >
          <div style={{ display: 'flex', gap: 56 }}>
            {CORE_METRICS.slice(0, 3).map((metric) => (
              <div key={metric.label} style={{ display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', fontSize: 44, fontWeight: 700, color: '#E6EDF7' }}>
                  {metric.value}
                </div>
                <div
                  style={{
                    display: 'flex',
                    fontSize: 19,
                    color: '#566072',
                    letterSpacing: 2,
                    textTransform: 'uppercase',
                    marginTop: 6,
                  }}
                >
                  {metric.label}
                </div>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', fontSize: 20, color: '#3D78FF' }}>
            commit {MEASURED_SHA}
          </div>
        </div>
      </div>
    ),
    size,
  )
}

import { ImageResponse } from 'next/og'

export const size = { width: 32, height: 32 }
export const contentType = 'image/png'

/* Same static-export opt-in the OG image needs — metadata images compile to
   Route Handlers. Exported as `out/icon` with no extension; the backend maps
   that name to image/png explicitly. */
export const dynamic = 'force-static'

/** The mark from the nav, reduced to a filled facet so it survives 16px. */
export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#F3F8F7',
        }}
      >
        <div
          style={{
            width: 17,
            height: 17,
            background: '#174A67',
            border: '2px solid #B54632',
            transform: 'rotate(45deg)',
            display: 'flex',
          }}
        />
      </div>
    ),
    size,
  )
}

import type { Metadata, Viewport } from 'next'
import Nav from '@/components/Nav'
import Footer from '@/components/Footer'
import '@fontsource/space-grotesk/latin-500.css'
import '@fontsource/space-grotesk/latin-600.css'
import '@fontsource/space-grotesk/latin-700.css'
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-600.css'
import '@fontsource/jetbrains-mono/latin-400.css'
import '@fontsource/jetbrains-mono/latin-500.css'
import '@fontsource/jetbrains-mono/latin-700.css'
import '@fontsource/newsreader/latin-400.css'
import '@fontsource/newsreader/latin-500.css'
import '@fontsource/newsreader/latin-600.css'
import './globals.css'

import { SITE_URL } from '@/lib/site'

const DESCRIPTION =
  'Sapphire is agent-native market intelligence that makes every observation inspectable: ' +
  'source, freshness, falsifier, confidence, and explicitly bounded authority.'

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'Sapphire Alpha — Evidence Intelligence',
    template: '%s — Sapphire Alpha',
  },
  description: DESCRIPTION,
  applicationName: 'Sapphire Alpha Evidence Intelligence',
  keywords: [
    'agent-native market intelligence',
    'market evidence provenance',
    'decision observatory',
    'falsifiable research',
    'verifiable systems',
    'bounded execution',
  ],
  authors: [{ name: 'Sapphire Alpha' }],
  creator: 'Sapphire Alpha',
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    url: SITE_URL,
    siteName: 'Sapphire Alpha',
    title: 'Sapphire Alpha — Evidence Intelligence',
    description: DESCRIPTION,
    locale: 'en_US',
    images: [
      {
        url: '/og.png',
        width: 1200,
        height: 630,
        alt: 'Sapphire Alpha evidence intelligence truth rail',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Sapphire Alpha — Evidence Intelligence',
    description: DESCRIPTION,
    images: ['/og.png'],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, 'max-image-preview': 'large' },
  },
  category: 'technology',
}

export const viewport: Viewport = {
  themeColor: '#F3F8F7',
  colorScheme: 'light',
  width: 'device-width',
  initialScale: 1,
}

const jsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Organization',
      '@id': `${SITE_URL}/#organization`,
      name: 'Sapphire Alpha',
      url: SITE_URL,
      description: DESCRIPTION,
      slogan: 'Markets are noisy. The evidence should not be.',
    },
    {
      '@type': 'WebSite',
      '@id': `${SITE_URL}/#website`,
      url: SITE_URL,
      name: 'Sapphire Alpha',
      description: DESCRIPTION,
      publisher: { '@id': `${SITE_URL}/#organization` },
      inLanguage: 'en-US',
    },
  ],
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <div className="aurora" aria-hidden="true" />
        <div className="field" aria-hidden="true" />
        <div className="grain" aria-hidden="true" />

        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[100] focus:bg-signal-coral focus:px-4 focus:py-2 focus:font-mono focus:text-xs focus:text-glacier"
        >
          Skip to content
        </a>

        <Nav />
        <main id="main">{children}</main>
        <Footer />
      </body>
    </html>
  )
}

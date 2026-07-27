import type { Metadata, Viewport } from 'next'
import { Space_Grotesk, Inter, JetBrains_Mono, Newsreader } from 'next/font/google'
import Nav from '@/components/Nav'
import Footer from '@/components/Footer'
import './globals.css'

/* Self-hosted at build time by next/font: no runtime request to Google, no
   layout shift, and nothing for a strict CSP to block. */
const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  weight: ['500', '600', '700'],
  variable: '--font-space-grotesk',
  display: 'swap',
})

const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-inter',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '700'],
  variable: '--font-jetbrains-mono',
  display: 'swap',
})

const newsreader = Newsreader({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-newsreader',
  display: 'swap',
})

import { SITE_URL } from '@/lib/site'

const DESCRIPTION =
  'Mission control for a self-sovereign multi-rail trading plant: free-reign agentic execution, ' +
  'Super Heavy orchestration, VPIN risk, live plant mesh, and research — designated capital only.'

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'Sapphire Alpha — Mission Control',
    template: '%s — Sapphire Alpha',
  },
  description: DESCRIPTION,
  applicationName: 'Sapphire Alpha',
  keywords: [
    'autonomous trading infrastructure',
    'agent orchestration',
    'verifiable systems',
    'Arbitrum Orbit',
    'Robinhood Chain',
    'FastAPI',
    'quantitative infrastructure',
  ],
  authors: [{ name: 'Sapphire Alpha' }],
  creator: 'Sapphire Alpha',
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    url: SITE_URL,
    siteName: 'Sapphire Alpha',
    title: 'Sapphire Alpha — Mission Control',
    description: DESCRIPTION,
    locale: 'en_US',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Sapphire Alpha — Mission Control',
    description: DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, 'max-image-preview': 'large' },
  },
  category: 'technology',
}

export const viewport: Viewport = {
  themeColor: '#04070d',
  colorScheme: 'dark',
  width: 'device-width',
  initialScale: 1,
}

/* JSON-LD. Kept minimal and truthful — an Organization plus the site itself.
   Claiming schema types the site cannot back up is the structured-data
   equivalent of an unverifiable metric. */
const jsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Organization',
      '@id': `${SITE_URL}/#organization`,
      name: 'Sapphire Alpha',
      url: SITE_URL,
      description: DESCRIPTION,
      slogan: 'Verify, don’t trust.',
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
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable} ${newsreader.variable}`}
    >
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
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[100] focus:bg-sapphire focus:px-4 focus:py-2 focus:font-mono focus:text-xs focus:text-void"
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

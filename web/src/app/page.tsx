import Link from 'next/link'
import SystemTopology from '@/components/SystemTopology'
import LiveIntelligence from '@/components/LiveIntelligence'
import ResearchSection from '@/components/ResearchSection'
import PortfolioProof from '@/components/PortfolioProof'
import AboutSection from '@/components/AboutSection'

/**
 * Single-page dashboard. Five sections chained together by section anchors so
 * the URL stays canonical and the nav is just fragments. Motion is CSS only;
 * the two live sections hydrate client-side against /api/v1/live.
 */

export default function Home() {
  return (
    <>
      <section id="hero" className="hero" aria-labelledby="hero-title">
        <div className="hero-inner">
          <p className="hero-kicker">Sapphire Alpha · live decision observatory</p>
          <h1 id="hero-title" className="hero-title">
            A trading system<span>you can watch work.</span>
          </h1>
          <p className="hero-lede">
            Four networked machines observe markets around the clock. Five
            strategies write down their claims — with the source, the age, and
            what would prove them wrong — and no capital moves until a human
            authorizes it with one tap. Every number on this page is either
            live from an endpoint or ships with the command that produced it.
          </p>
          <div className="hero-actions">
            <a href="#system" className="hero-action hero-action--primary">
              See the system
            </a>
            <Link href="/dashboard" className="hero-action">
              Open the observatory
            </Link>
          </div>
          <p className="hero-source">
            Source: <code>/api/v1/live</code> · authority: none ·{' '}
            unknown stays unknown.
          </p>
        </div>
        <div className="hero-scroll" aria-hidden="true">
          <span>Scroll</span>
          <svg width="14" height="24" viewBox="0 0 14 24">
            <rect x="0.5" y="0.5" width="13" height="23" rx="6.5" />
            <line x1="7" y1="6" x2="7" y2="11" />
          </svg>
        </div>
      </section>

      <SystemTopology />
      <LiveIntelligence />
      <ResearchSection />
      <PortfolioProof />
      <AboutSection />
    </>
  )
}

import { SITE_URL } from '@/lib/site'

/**
 * Short about section. The site has never been about selling a person; the
 * argument is the record. This block gives a reader one paragraph, one city,
 * and one URL — enough to know who is behind the work and where to find them.
 */
export default function AboutSection() {
  return (
    <section id="about" className="section about" aria-labelledby="about-title">
      <header className="section-head">
        <p className="section-kicker">05 · About</p>
        <h2 id="about-title" className="section-title">
          Built by one person.<span>Held to the same rules.</span>
        </h2>
      </header>

      <div className="about-grid">
        <div className="about-copy">
          <p>
            <strong>Ari Spector</strong> designs and operates the Sapphire mesh
            from Houston, Texas. The system is small on purpose — one commander,
            one GPU executor, two edge sensors — because every extra node is a
            surface an operator has to keep honest.
          </p>
          <p>
            The public site is a contract, not a brochure. Numbers ship with the
            commands that reproduce them; live values are read from
            {' '}
            <code>/api/v1/live</code> and unknown stays unknown. If a claim on
            this page cannot be checked, treat it as fiction.
          </p>
          <p className="about-actions">
            <a href="mailto:ari@sapphirealpha.xyz" className="about-action about-action--primary">
              ari@sapphirealpha.xyz
            </a>
            <a href={SITE_URL} className="about-action">
              sapphirealpha.xyz
            </a>
          </p>
        </div>

        <dl className="about-facts">
          <div>
            <dt>Location</dt>
            <dd>Houston, TX · US-Central1</dd>
          </div>
          <div>
            <dt>Stack</dt>
            <dd>FastAPI · Next.js · Ollama · Cloud Run</dd>
          </div>
          <div>
            <dt>Settlement</dt>
            <dd>Robinhood Chain (Orbit L3, id 4663)</dd>
          </div>
          <div>
            <dt>Authority</dt>
            <dd>Telegram, one tap per order</dd>
          </div>
        </dl>
      </div>
    </section>
  )
}

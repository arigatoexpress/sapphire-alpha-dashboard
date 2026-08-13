import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'

import App from '../App'

function render(path = '/dashboard/') {
  return renderToStaticMarkup(<App initialPath={path} />)
}

describe('system story dashboard', () => {
  it('opens with one clear, nontechnical system story', () => {
    const markup = render()

    expect(markup).toContain('One conversation.')
    expect(markup).toContain('An entire system')
    expect(markup).toContain('one personal assistant')
    expect(markup).toContain('From a message to a trusted result.')
    expect(markup).toContain('Private by default')
    expect(markup).toContain('Evidence over theater')
    expect(markup).toContain('Human at the boundary')
    expect(markup).toContain('Anonymous · read-only · no private vault contents')
  })

  it('links every dashboard page with a real route', () => {
    const markup = render()

    for (const route of [
      '/dashboard/',
      '/dashboard/architecture',
      '/dashboard/pipeline',
      '/dashboard/models',
      '/dashboard/ai-today',
    ]) {
      expect(markup).toContain(`href="${route}"`)
    }
  })

  it('keeps the public surface read-only and credential-free', () => {
    const markup = render()

    expect(markup).toContain('Read-only')
    expect(markup).toContain('No public command surface.')
    expect(markup).not.toMatch(/type="password"|autocomplete="username"|Authorization|btoa\s*\(/i)
    expect(markup).not.toMatch(/chat[_ -]?id|wallet address|private key|seed phrase/i)
  })

  it('links to the admitted public observation without presenting absence as health', () => {
    const markup = render()

    expect(markup).toContain('Public observation')
    expect(markup).toContain('href="/api/v1/live"')
    expect(markup).toContain('Absence is shown honestly')
    expect(markup).not.toContain('All systems healthy')
  })
})

describe('dashboard subpages', () => {
  it('explains architecture and the owner boundary', () => {
    const markup = render('/dashboard/architecture')

    expect(markup).toContain('A home AI system with one front door.')
    expect(markup).toContain('Preparation can be automatic. Impact is not.')
    expect(markup).toContain('Can proceed')
    expect(markup).toContain('Needs approval')
    expect(markup).toContain('One owner. One poller. One source of truth.')
  })

  it('turns the request pipeline into six plain-English steps', () => {
    const markup = render('/dashboard/pipeline')

    for (const title of [
      'Ask naturally',
      'Understand the job',
      'Choose the engine',
      'Research and verify',
      'Pause before impact',
      'Report back',
    ]) {
      expect(markup).toContain(title)
    }
    for (const field of ['Outcome', 'Evidence', 'Blocker', 'Next']) {
      expect(markup).toContain(field)
    }
  })

  it('distinguishes the framework, local models, frontier services, and memory', () => {
    const markup = render('/dashboard/models')

    expect(markup).toContain('The conductor is not the model.')
    expect(markup).toContain('OpenClaw')
    expect(markup).toContain('Ollama + open-weight models')
    expect(markup).toContain('Codex + selected APIs')
    expect(markup).toContain('The knowledge vault')
    expect(markup).toContain('New models are candidates, not deployed capabilities.')
  })

  it('publishes an anonymous AI pattern map without named research inputs', () => {
    const markup = render('/dashboard/ai-today')

    expect(markup).toContain('current pattern map')
    expect(markup).toContain('Patterns here; named source trails stay private.')
    expect(markup).toContain('Briefs are becoming scheduled services')
    expect(markup).toContain('Open-weight models strengthen the private lane')
    for (const namedSource of ['xAI', 'Grok', 'Meta', 'Muse', 'Moonshot', 'Kimi', 'Limitless']) {
      expect(markup).not.toContain(namedSource)
    }
    expect(markup).not.toContain('https://')
  })

  it('falls back to the overview for an unknown dashboard path', () => {
    expect(render('/dashboard/not-a-real-page')).toContain('One conversation.')
  })
})

describe('build truth', () => {
  it('never invents a deployed build identity', () => {
    const markup = render()

    expect(markup).toContain('Build not yet attributed')
    expect(markup).toContain('href="/api/build"')
  })
})

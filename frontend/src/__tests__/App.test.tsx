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
    expect(markup).toContain('Muse Spark 1.1—not “Muse Glimmer.”')
    expect(markup).not.toContain('Muse Spark is open source')
  })

  it('publishes a current primary-source AI brief with the Grok identity distinction', () => {
    const markup = render('/dashboard/ai-today')

    expect(markup).toContain('verified 13 Aug 2026')
    expect(markup).toContain('Grok 4.6 is an API model. Grok Bot is a separate cloud product.')
    expect(markup).toContain('grok-4.6')
    expect(markup).toContain('not a published local CLI, SDK, or drop-in OpenClaw bridge')
    expect(markup).toContain('Muse Spark 1.1 is an agent model, not a downloadable open model')
    expect(markup).toContain('Kimi K3 pushes the open-weight lane forward')
    expect(markup).toContain('https://github.com/xai-org/xai-sdk-python/releases/tag/v1.18.0')
    expect(markup).toContain('https://x.ai/bot')
    expect(markup).toContain('https://ai.meta.com/blog/introducing-muse-spark-meta-model-api/')
    expect(markup).toContain('https://github.com/MoonshotAI/Kimi-K3')
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

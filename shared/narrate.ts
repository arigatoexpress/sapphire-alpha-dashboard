/**
 * Snapshot -> English. Pure, no clock, no DOM, no fetch.
 *
 * This is the "a normal person can tell what is going on" feature, written as a
 * function so it can be tested instead of admired. The hard rule: **never emit a
 * sentence the snapshot does not support.** If a snapshot is old, say that and
 * stop — do not describe a stale reading in the present tense. If no link
 * reports a latency, do not mention latency. If nothing is moving, say nothing
 * is moving.
 */

import { describeNode, phrase } from './vocabulary'
import type { LiveSnapshot } from './telemetry'

export type NarrationTone = 'empty' | 'stale' | 'degraded' | 'healthy'

export interface Narration {
  tone: NarrationTone
  sentences: string[]
  /** The sentences joined with single spaces, for a one-line narrator strip. */
  text: string
}

/** Matches `DEFAULT_STALE_AFTER_SECONDS` in backend/live_telemetry.py. */
export const STALE_AFTER_SECONDS = 180

const NUMBER_WORDS = [
  'Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six',
  'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve',
]

function count(value: number): string {
  return value >= 0 && value < NUMBER_WORDS.length ? NUMBER_WORDS[value] : String(value)
}

function lower(word: string): string {
  return word.charAt(0).toLowerCase() + word.slice(1)
}

function list(items: string[]): string {
  if (items.length === 0) return ''
  if (items.length === 1) return items[0]
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}

function nodePhrase(id: string): string {
  return `the ${phrase(describeNode(id))}`
}

function isEmpty(snapshot: LiveSnapshot): boolean {
  if (snapshot.observed_at === null) return true
  if (snapshot.status === 'offline' || snapshot.status === 'warming') return true
  return snapshot.nodes.length === 0 && snapshot.links.length === 0 && snapshot.agents.length === 0
}

function isStale(snapshot: LiveSnapshot): boolean {
  if (snapshot.status === 'stale') return true
  return snapshot.freshness_s !== null && snapshot.freshness_s > STALE_AFTER_SECONDS
}

function ageSentence(freshnessS: number | null): string {
  if (freshnessS === null) return 'The last report from the system is out of date.'
  if (freshnessS < 120) {
    const seconds = Math.round(freshnessS)
    return `The last report from the system arrived ${seconds} ${seconds === 1 ? 'second' : 'seconds'} ago.`
  }
  const minutes = Math.round(freshnessS / 60)
  return `The last report from the system arrived ${minutes} ${minutes === 1 ? 'minute' : 'minutes'} ago.`
}

function flowSentence(snapshot: LiveSnapshot): string {
  let busiest = null as LiveSnapshot['links'][number] | null
  for (const link of snapshot.links) {
    if (
      link.event_rate !== null &&
      link.event_rate > 0 &&
      (
        busiest === null ||
        busiest.event_rate === null ||
        link.event_rate > busiest.event_rate
      )
    ) {
      busiest = link
    }
  }
  if (busiest === null) {
    const measured = snapshot.links.some((link) => link.event_rate !== null)
    return measured
      ? 'No measured connection is moving right now.'
      : 'No connection supplied a traffic measurement in this report.'
  }
  // The selection above proves this is a measured positive number. Keep that
  // proof explicit: a null-coalescing zero here would make a future control-flow
  // regression read "unknown" as "quiet".
  if (busiest.event_rate === null) {
    return 'No connection supplied a traffic measurement in this report.'
  }
  const rate = Math.round(busiest.event_rate)
  const pace = rate === 1 ? 'about one event a minute' : `about ${rate} events a minute`
  return `The busiest measured connection links ${nodePhrase(busiest.source)} to ${nodePhrase(busiest.target)} at ${pace}.`
}

function agentSentence(snapshot: LiveSnapshot): string {
  const working = snapshot.summary.active_agents
  if (working === null) {
    return 'The report did not include an active task-agent count.'
  }
  if (working === 0) return 'No task agents are active right now.'
  return `${count(working)} task ${working === 1 ? 'agent is' : 'agents are'} active.`
}

function troubleSentences(snapshot: LiveSnapshot): string[] {
  const sentences: string[] = []
  const groups: Array<{ status: 'down' | 'degraded'; verb: string }> = [
    { status: 'down', verb: 'not reporting' },
    { status: 'degraded', verb: 'having trouble' },
  ]
  for (const group of groups) {
    const hit = snapshot.nodes.filter((node) => node.status === group.status)
    if (hit.length === 0) continue
    const names = hit.slice(0, 3).map((node) => nodePhrase(node.id))
    if (hit.length === 1) {
      const description = describeNode(hit[0].id)
      const verb = description.plural ? 'are' : 'is'
      sentences.push(`${names[0].charAt(0).toUpperCase()}${names[0].slice(1)} ${verb} ${group.verb}.`)
    } else if (hit.length <= 3) {
      sentences.push(`${count(hit.length)} parts are ${group.verb}: ${list(names)}.`)
    } else {
      sentences.push(`${count(hit.length)} parts are ${group.verb}, including ${list(names)}.`)
    }
  }
  return sentences
}

function attentionSentence(snapshot: LiveSnapshot): string {
  const waiting = snapshot.summary.attention
  if (waiting === null) return 'The report did not include a count of decisions waiting for a person.'
  if (waiting <= 0) return 'Nothing is waiting on you.'
  return `${count(waiting)} ${waiting === 1 ? 'thing is' : 'things are'} waiting for a person to decide.`
}

function finish(tone: NarrationTone, sentences: string[]): Narration {
  return { tone, sentences, text: sentences.join(' ') }
}

export function narrate(snapshot: LiveSnapshot): Narration {
  if (isEmpty(snapshot)) {
    return finish('empty', [
      'No live report has arrived yet.',
      'Nothing is being measured right now, so there is nothing to show.',
    ])
  }

  if (isStale(snapshot)) {
    return finish('stale', [
      ageSentence(snapshot.freshness_s),
      'What you see is that old report, not what the system is doing right now.',
    ])
  }

  const trouble = troubleSentences(snapshot)
  const tone: NarrationTone =
    snapshot.summary.state === 'degraded' || trouble.length > 0 ? 'degraded' : 'healthy'

  return finish(tone, [
    flowSentence(snapshot),
    agentSentence(snapshot),
    ...trouble,
    attentionSentence(snapshot),
  ])
}

/* `lower` is exported for renderers that need to embed a plain name in prose of
   their own without re-deriving the rule. */
export { lower as lowerFirstWord }

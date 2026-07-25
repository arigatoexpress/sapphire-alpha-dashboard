/**
 * Plain English for every id the live snapshot can contain.
 *
 * The rule this file exists to enforce: a visitor should never have to know what
 * MOSS, RAG, a tier probe or a killswitch is, and should never see a raw slug on
 * screen. Every name here is written for someone who has never seen the system.
 *
 * The lookups are **total**. An id with no entry returns `UNDESCRIBED` with
 * `known: false` — a visible defect, not a silent passthrough of the raw id.
 * `shared/__tests__/vocabulary.test.ts` asserts every id in a real captured
 * snapshot has an entry, so adding a node without a name breaks the build.
 */

import { linkId, type LiveLink } from './telemetry'

export interface VocabularyEntry {
  /** A short noun phrase, sentence case, safe to render as a label. */
  plainName: string
  /** One sentence answering "what is this?" for a non-technical visitor. */
  oneLiner: string
  /** True when `plainName` is a proper noun and must not be lowercased mid-sentence. */
  proper?: boolean
}

export interface Described extends VocabularyEntry {
  id: string
  known: boolean
}

/** The loud fallback. Deliberately reads as a defect. */
export const UNDESCRIBED: VocabularyEntry = {
  plainName: 'Missing description',
  oneLiner:
    'Something new appeared here and nobody has written a plain English name for it yet.',
}

export const NODE_VOCABULARY: Record<string, VocabularyEntry> = {
  'public-edge': {
    plainName: 'Public website',
    oneLiner: 'The page you are reading, and the front door for everything behind it.',
  },
  orchestration: {
    plainName: 'Job scheduler',
    oneLiner: 'Decides what work happens next and hands each job to whoever can do it.',
  },
  'gpu-compute': {
    plainName: 'Home graphics card',
    oneLiner:
      'The chip in the home computer that runs the AI models, so questions never leave the house.',
  },
  intelligence: {
    plainName: 'Thinking agents',
    oneLiner: 'The pool of AI helpers that read, write, check and decide things.',
  },
  markets: {
    plainName: 'Trading desk',
    oneLiner: 'Watches live market prices and keeps a paper record of what it would have done.',
  },
  archive: {
    plainName: 'Knowledge archive',
    oneLiner: 'Everything the system has learned and written down, kept for later.',
  },
  'win-workhorse': {
    plainName: 'Home desktop computer',
    oneLiner: 'The machine that stays awake at home so there is always somewhere to send work.',
  },
  'agent-worker': {
    plainName: 'Task runner',
    oneLiner: 'Picks jobs off the queue one at a time and sees each of them through.',
  },
  'telegram-bot': {
    plainName: 'Chat assistant',
    oneLiner: 'Sends a phone message when a person needs to decide something, and waits for a reply.',
  },
  'ollama-inference': {
    plainName: 'Local model runner',
    oneLiner: 'Loads the AI models on the home machine and answers the questions put to them.',
  },
  'knowledge-archive': {
    plainName: 'Searchable notes library',
    oneLiner: 'The written notes, indexed so an agent can look something up in a second.',
  },
}

export const LINK_VOCABULARY: Record<string, VocabularyEntry> = {
  'public-edge->orchestration': {
    plainName: 'Website asking for an update',
    oneLiner: 'The page you are reading asks the scheduler what the system is doing right now.',
  },
  'orchestration->gpu-compute': {
    plainName: 'Work sent to the home machine',
    oneLiner: 'The scheduler hands a job to the home computer to think about.',
  },
  'gpu-compute->intelligence': {
    plainName: 'Answers going back to the agents',
    oneLiner: 'The home computer returns what it worked out to the helper that asked.',
  },
  'intelligence->markets': {
    plainName: 'Agents watching the market',
    oneLiner: 'The helpers read live prices and note what they would have done about them.',
  },
  'intelligence->archive': {
    plainName: 'Agents writing things down',
    oneLiner: 'Anything the helpers work out gets saved so it is not learned twice.',
  },
  'telegram-bot->agent-worker': {
    plainName: 'Chat message becoming a job',
    oneLiner: 'A message sent from a phone turns into a piece of work for the system to do.',
  },
  'agent-worker->ollama-inference': {
    plainName: 'Job asking the model a question',
    oneLiner: 'The task runner puts a question to an AI model running on the home machine.',
  },
  'ollama-inference->win-workhorse': {
    plainName: 'Model using the home computer',
    oneLiner: 'Running the model uses the home desktop, which is where the heavy work happens.',
  },
  'agent-worker->knowledge-archive': {
    plainName: 'Job looking something up',
    oneLiner: 'The task runner searches the written notes before answering from scratch.',
  },
}

export const AGENT_VOCABULARY: Record<string, VocabularyEntry> = {
  code: {
    plainName: 'Programmer',
    oneLiner: 'Writes new code when something needs building.',
  },
  'code-edit': {
    plainName: 'Code editor',
    oneLiner: 'Makes careful changes to code that already exists.',
  },
  coder: {
    plainName: 'Second programmer',
    oneLiner: 'A spare writer of code, used when the first one is busy.',
  },
  'deep-reasoning': {
    plainName: 'Slow careful thinker',
    oneLiner: 'Takes the hard questions and works through them step by step.',
  },
  embed: {
    plainName: 'Note indexer',
    oneLiner: 'Turns written notes into something the system can search by meaning.',
  },
  embeddings: {
    plainName: 'Second note indexer',
    oneLiner: 'A spare indexer, so searching the notes keeps working if one stops.',
  },
  fast: {
    plainName: 'Quick responder',
    oneLiner: 'Handles the easy questions immediately instead of queueing them.',
  },
  'fast-triage': {
    plainName: 'Sorter',
    oneLiner: 'Reads what came in and decides who should deal with it.',
  },
  'long-context': {
    plainName: 'Long document reader',
    oneLiner: 'Reads very long documents in one go and summarises them.',
  },
  reasoning: {
    plainName: 'Everyday thinker',
    oneLiner: 'Works through ordinary questions that do not need the slow thinker.',
  },
  review: {
    plainName: 'Checker',
    oneLiner: 'Reads work another helper produced and looks for mistakes in it.',
  },
  vision: {
    plainName: 'Picture reader',
    oneLiner: 'Looks at images and screenshots and describes what is in them.',
  },
  'chain-poll': {
    plainName: 'Ledger watcher',
    oneLiner: 'Keeps checking the public trading ledger for anything new.',
  },
  orderflow: {
    plainName: 'Order watcher',
    oneLiner: 'Watches who is buying and selling, and how much.',
  },
  'feed-listen': {
    plainName: 'Price listener',
    oneLiner: 'Stays connected to the live price feed and passes on what arrives.',
  },
  'clean-watchlist': {
    plainName: 'Watchlist tidier',
    oneLiner: 'Drops things from the watchlist once they stop being worth watching.',
  },
  'fresh-decay': {
    plainName: 'Staleness checker',
    oneLiner: 'Marks readings as old so nothing is trusted longer than it should be.',
  },
  'metrics-advisory': {
    plainName: 'Numbers reporter',
    oneLiner: 'Adds up how the system is doing and reports it, without ever acting on it.',
  },
  'social-signal': {
    plainName: 'Public chatter reader',
    oneLiner: 'Reads what people are saying publicly and passes on anything notable.',
  },
  'visualizer-serve': {
    plainName: 'Chart maker',
    oneLiner: 'Turns the collected numbers into the pictures shown on this site.',
  },
  'gpu-workhorse': {
    plainName: 'Home computer helper',
    oneLiner: 'Keeps the home machine busy with whatever work is queued for it.',
  },
  'agent-worker': {
    plainName: 'Task runner',
    oneLiner: 'Picks jobs off the queue one at a time and sees each of them through.',
  },
  'telegram-command-bot': {
    plainName: 'Chat assistant',
    oneLiner: 'Sends a phone message when a person needs to decide something, and waits for a reply.',
  },
  'ollama-inference-host': {
    plainName: 'Local model runner',
    oneLiner: 'Loads the AI models on the home machine and answers the questions put to them.',
  },
}

function describe(table: Record<string, VocabularyEntry>, id: string): Described {
  const entry = table[id]
  if (entry) return { id, known: true, ...entry }
  return { id, known: false, ...UNDESCRIBED }
}

export function describeNode(id: string): Described {
  return describe(NODE_VOCABULARY, id)
}

export function describeLink(link: Pick<LiveLink, 'source' | 'target'>): Described {
  return describe(LINK_VOCABULARY, linkId(link))
}

export function describeAgent(id: string): Described {
  return describe(AGENT_VOCABULARY, id)
}

/**
 * The plain name as it should read inside a sentence: `the trading desk`, but
 * `Robinhood Chain` if it is ever marked as a proper noun.
 */
export function phrase(entry: VocabularyEntry): string {
  if (entry.proper) return entry.plainName
  return entry.plainName.charAt(0).toLowerCase() + entry.plainName.slice(1)
}

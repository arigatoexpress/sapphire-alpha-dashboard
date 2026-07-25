import fs from 'node:fs'
import path from 'node:path'
import matter from 'gray-matter'
import { marked } from 'marked'
import sanitizeHtml from 'sanitize-html'

/* Reports are partly agent-authored (Grok for methodology, Kimi for dossiers),
   so the markdown is not trusted input even though it lives in this repo. Raw
   HTML in a generated file would otherwise execute on our own domain. Tables
   are allowed because the analysis leans on them heavily. */
const SANITIZE_OPTIONS: sanitizeHtml.IOptions = {
  allowedTags: [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'a', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
    'em', 'strong', 'del', 'hr', 'br',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img', 'figure', 'figcaption',
  ],
  allowedAttributes: {
    a: ['href', 'title'],
    img: ['src', 'alt', 'title'],
    th: ['align'],
    td: ['align'],
    code: ['class'],
  },
  allowedSchemes: ['http', 'https', 'mailto'],
  // Drop the contents of anything disallowed rather than leaving stray text.
  nonTextTags: ['style', 'script', 'textarea', 'option', 'noscript'],
}

/**
 * Published research, read from `web/content/research/` at build time.
 *
 * That directory is populated only by `web/scripts/sync-research.sh`, which
 * copies a vault file solely when its frontmatter carries `publish: true`. The
 * corpus is committed, so what the site serves is reviewable in git rather than
 * assembled during deploy — and the vault's auto-generated notes, which
 * hallucinate, can never reach the site by accident.
 */

const CONTENT_DIR = path.join(process.cwd(), 'content', 'research')

/* IMPORTANT: the corpus must never be empty. `output: export` fails the build
   when generateStaticParams() for /research/[slug] returns no entries, with the
   misleading message "missing generateStaticParams()". `how-research-is-published.md`
   is permanent site content committed here for that reason — the sync script only
   adds vault files, so it can never remove the last entry. Do not delete it. */

export type Report = {
  slug: string
  title: string
  description: string
  /** ISO date string, or null when the report omitted one. */
  date: string | null
  tags: string[]
  /** Rendered HTML body. */
  html: string
  /** Rough read time in minutes, floored at 1. */
  minutes: number
}

export type ReportSummary = Omit<Report, 'html'>

function slugify(filename: string): string {
  return filename
    .replace(/\.md$/i, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function readAll(): Report[] {
  if (!fs.existsSync(CONTENT_DIR)) return []

  return fs
    .readdirSync(CONTENT_DIR)
    .filter((name) => name.toLowerCase().endsWith('.md'))
    .map((name) => {
      const raw = fs.readFileSync(path.join(CONTENT_DIR, name), 'utf-8')
      const { data, content } = matter(raw)

      // Defence in depth: the sync script gates on this, and so does the reader.
      // A file hand-dropped into the corpus still cannot publish without opting in.
      if (data.publish !== true) return null

      const words = content.trim().split(/\s+/).length

      return {
        slug: slugify(name),
        title: String(data.title ?? name.replace(/\.md$/i, '')),
        description: String(data.description ?? ''),
        date: data.date ? new Date(data.date).toISOString().slice(0, 10) : null,
        tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
        html: sanitizeHtml(marked.parse(content, { async: false }) as string, SANITIZE_OPTIONS),
        minutes: Math.max(1, Math.round(words / 220)),
      }
    })
    .filter((report): report is Report => report !== null)
    .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
}

export function getReports(): ReportSummary[] {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  return readAll().map(({ html, ...summary }) => summary)
}

export function getReport(slug: string): Report | null {
  return readAll().find((report) => report.slug === slug) ?? null
}

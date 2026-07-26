# Design — The Machine Room: un-redact the system and make it legible

**Date:** 2026-07-25
**Status:** implemented and locally verified; awaiting PR CI and the explicit production deploy gate
**Repo:** `sapphire-alpha-dashboard`
**Executor:** Codex with parallel implementation agents after the Claude/Kimi usage handoff
**Orchestrator:** Codex — verifies, reviews, and lands the reversible PR

Implementation note: link throughput is now published only when a collector can
measure it from a bounded log or directory window. `event_rate: null` is the
honest result when that observation is unavailable. Latency is likewise measured
by a configured probe or left unobserved. The earlier design language that called
every rate "real" was too strong for the pre-existing collector.

---

## 1. The problem, stated correctly

The site is **not gated. It is redacted.** `PUBLIC_READ_ONLY=1` is already set in prod
(`cloudbuild.yaml:30`), so anonymous visitors already get in. What they get is
`public_projection()` (`backend/live_telemetry.py:387`): every number replaced by an adjective
(`load_band`, `latency_band`, `activity_band`, `freshness_band`) and the whole snapshot delayed
15 seconds.

That redaction is the direct cause of "bland" and "not understandable." A latency figure that
jitters between 34 ms and 51 ms reads as *alive*. The word `"fast"` reads as a brochure. The
system was made boring on purpose, for a safety reason that does not survive contact with what is
actually in the payload.

And the payload is already the thing we want to draw. `/api/v1/live` returns:

```
nodes[]   id, zone, label, status, load_band|load, activity_rate, freshness_s
links[]   source, target, status, latency_ms, event_rate, signal_class
agents[]  role, state, activity, verification, provider_class
markets{} network, status, feed_age_s, paper_strategies, decision_gate, execution
events[]  (already unredacted in both views)
```

That is a live route ledger with per-link latency and event rate. Nobody has to invent a
data model. The work is to stop hiding it and render every route in a lane that stays legible.

## 2. Decisions (Ari, 2026-07-25)

| # | Decision |
|---|---|
| D1 | **Un-redact everything except capital.** Delete `live_telemetry.public_projection`; zero the public delay. `moss_telemetry` keeps `_usdm_band` — the exact USDm balance stays banded. |
| D2 | **Publish a sanitized vault map.** New public artifact with **zero** personally identifying information — the only identity anywhere on the site is the GitHub handle. Raw `/vault/rag-map` stays behind auth. |
| D3 | **Hero on `/`, depth on `/dashboard`.** Two renderers, one shared data contract and one shared vocabulary. |
| D4 | **Kimi implements from a written brief; Ari dispatches; Claude verifies and lands.** |
| D5 | **x402 is future, not now.** Design the public vault endpoint so a paid/programmatic tier can be added later without rework. Build no payment code in this cycle. |
| D6 | **Ari's thesis is the mandate.** Cowen is the primary current-cycle lens; Hayes, Bankless, Limitless, and Nadeau have bounded advisory domains. No analyst can set conviction or authorize execution. |
| D7 | **The dashboard is a route ledger, not a free-form graph.** Each link owns a non-crossing row at every viewport; no SVG geometry or decorative motion. |

Wallet identity needs no decision: it is masked at *ingest* (`moss_telemetry.py:101`, regex-validated
`identity_masked`), so no address exists in the payload to leak. Un-redaction cannot expose it.

## 3. Architecture

Three pure modules in `shared/` are consumed by both surfaces. The dashboard adds a
table-like route renderer whose DOM order is the non-overlap guarantee.

```
shared/
  theme.css        (exists)
  telemetry.ts     one TS type mirroring the un-redacted snapshot. Single source of truth.
  vocabulary.ts    node/link/agent id -> { plainName, oneLiner }. Both surfaces say the same words.
  narrate.ts       pure: snapshot -> English sentences. THE normie feature.
```

**Why pure functions:** "make it understandable for normies" is untestable as a styling goal and
trivially testable as `narrate(snapshot) === "The home GPU is answering the trading desk. Three
agents are working. Nothing is waiting on you."` Route legibility is structural: one route per
row, with endpoint, status, rate, and latency cells. There are no coordinates to collide.

**Renderers:**

- `web/src/components/MachineRoom.tsx` — the landing hero. Full-bleed live graph, client-side
  fetch + poll against `/api/v1/live`. `web/` is `output: 'export'` (static), so this must be a
  client component with no server dependency (`AGENTS.md`: never add a route handler to `web/`).
- `frontend/src/components/SignalRoutes.tsx` — dense operator route ledger, same vocabulary
  and narration, with exact measurements or `not observed`.

Both import from `shared/` via tsconfig path aliases. No new package, no build orchestration.

## 4. Work items

### W1 — Telemetry goes stale while the page is open *(bug; do first)*
A hero that dies after three minutes is worse than no hero, so this gates everything visual.
`frontend/src/App.tsx:443` flips at `ageS >= 900`. Commit `55d3f51` already shipped a scheduled
publisher for exactly this, so **this is a regression or an incomplete fix.** Three candidate causes,
to be distinguished by measurement, not guessed:

1. the publisher on the projector host stopped, or runs slower than 900 s;
2. the client fetches once and never re-polls, so `ageS` grows without bound against a snapshot
   that was fine when it arrived;
3. `observed_at` is *producer* time rather than *publish* time, so age is structurally inflated.

**Forbidden fix: raising the 900 s threshold.** That is the rejector-turned-verifier-by-threshold
move this stack has already made twice (`CONFIDENT_FLOOR`, nucleus Check C). A freshness check that
never fires is worse than none, because it reads as green.

### W2 — Delete the redaction tier
- `backend/live_telemetry.py`: delete `public_projection`; `get(public=…)` returns the full snapshot;
  delay → 0.
- `backend/main.py`: `auth_or_public` → public for **GET**. Non-GET still requires auth. Ingest
  (`POST /api/v1/telemetry`, `/api/v1/moss/telemetry`) keeps HMAC — un-redacting reads must not
  un-protect writes.
- `cloudbuild.yaml:30` / `deploy.sh:19`: `PUBLIC_TELEMETRY_DELAY_SECONDS=0`. `AUTH_*` stays (ingest
  + raw vault map still need it).
- `moss_telemetry.public_projection` **stays** (D1) — capital remains banded.

### W3 — Remove the login UI
`frontend/src/App.tsx:65-80,128` (`showLogin`, `authRequired`, `<Login>`) and every `public_view`
branch, including `:261`'s `'aggregated + delayed' : 'operator detail'`. There is no second tier
left to describe, so the copy describing one goes too.

### W4 — The Machine Room (hero on `/`)
Live graph as the first thing a visitor sees. Requirements that make it work for a non-technical
visitor, all of which are testable via `narrate`/`vocabulary`:
- every node carries a plain-language name and a one-line "what this is" — no bare hostnames;
- edges animate at their **real** `event_rate`, and show their **real** `latency_ms`;
- a narrator strip states, in one English sentence, what the system is doing right now;
- nothing on screen requires knowing what MOSS, RAG, a tier probe, or a killswitch is.

### W5 — Replace the overlapping graph
Delete `SignalLoom`, its geometry helper, resize hook, and SVG paths. Render `SignalRoutes`
as one semantic row per observed link. Verify row content in unit tests and inspect the real
build at 320 / 768 / 1440 widths.

### W6 — Sanitized public vault map
New generator emitting a topic/cluster graph from `~/Knowledge` with **no** personal identifiers:
no note titles naming people, places, accounts, employers, or family; no filesystem paths; no
dates tied to Ari's life. Topic and cluster structure only. Served at a new public route; raw
`/vault/rag-map` keeps `require_auth`.
**Enforced by a redaction eval**, not by care: a test that runs the generator over a fixture vault
seeded with PII and asserts none of it survives. Ari's GitHub handle is the sole permitted identity
string, site-wide.

### W7 — Research surface
`web/src/app/research/page.tsx` renders nothing because no posts exist. Wire real content through
the SSG path (`7e0c0ea` copies `web/content` into the build stage).

### W8 — Aesthetic pass
Whole-site, after W2–W5 settle the structure. Redesigning before the redaction tier is gone means
designing panels that are about to change shape.

## 5. Testing

Golden evals **before** the refactor, per the charter.

**Python (pytest, exists):**
- `GET /api/v1/live` anonymous returns `latency_ms`, `events_per_min`, `load`, `freshness_s`, and
  **no** `public_view`, `*_band`, or `public_policy` key anywhere in the tree;
- MOSS stays banded: `usdm_band` present **and** raw `usdm` absent — this is the D1 line, and it
  must have a test that fails loudly if a future cleanup "finishes the job";
- non-GET without credentials still 401s; ingest still rejects a bad HMAC;
- the sanitized vault map contains no PII from a seeded fixture.

**TypeScript (`vitest` in `frontend/`):**
- `narrate()` golden cases: healthy / degraded / stale / empty snapshots → expected sentences;
- `SignalRoutes` renders every route exactly once, includes source/target, rate and latency,
  and contains no SVG or animated path;
- `vocabulary` totality: every node and link id present in a real snapshot has an entry, so a new
  node can never silently render as a raw hostname.

Browser checks at 320 / 768 / 1440 remain mandatory because the failure being replaced was
visual: overlapping text and crossing paths.

## 6. Sequencing

W1 → W2 → W3 → (W4 ∥ W5) → W6 → W7 → W8.

W1 first because a stale hero is a broken hero. W2/W3 before W4/W5 because they delete surface the
redesign would otherwise be drawn against.

## 7. Fences for this job

- **No deploy.** `gcloud run deploy` and Cloud Build are gated (CLAUDE.md CRITICAL #1). Kimi
  branches, commits, and opens a PR. Ari 1-clicks the deploy.
- **THO / `Project-Go-Forward` untouched.** Different project, hard denylist.
- **No key material, no wallet writes, no trading paths.** This job is a website.
- **Stage explicit paths only.** Never `git add .` / `-A`.
- **`~/Knowledge` is read-only to this job.** W6 reads the vault to generate a map; it writes
  nothing back into it.

## 8. Deferred

- **x402** — a paid/programmatic access tier for the public data endpoints (D5). Endpoints should
  be shaped so a 402 tier drops in later; no payment code this cycle.
- Anything in `~/ops-state/ROADMAP-sapphire-frontend-rework-2026-07-25.md` not listed above.

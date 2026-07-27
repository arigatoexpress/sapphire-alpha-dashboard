# AGENTS.md — sapphire-alpha-dashboard

## Role
Two surfaces on one Cloud Run service:
- `/` — the **public marketing site** (`web/`), the front door for consulting and investor conversations.
- `/dashboard` — privacy-preserving **Mission Control** (`frontend/`) for the trading & business stack.

## Tech stack
- Backend: FastAPI + uvicorn (Python 3.11) — also serves both frontends as static files
- Marketing site (`web/`): Next.js 16 static export + Tailwind v4 + TypeScript
- Operator dashboard (`frontend/`): React 19 + Vite + TypeScript
- Hosting: Cloud Run (Docker / Cloud Build deploy), one image, one domain

### Why a static export
`next.config.ts` sets `output: 'export'`, so `web/` compiles to plain prerendered HTML in
`web/out/`. The FastAPI container serves that directory directly — no second service, no
reverse proxy, and every marketing route is a real HTML file for crawlers and unfurlers.
There is no Next.js server at runtime; do not add a route handler or server action to `web/`.

## Local dev
```bash
cd backend
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q

# Marketing site (produces web/out/, which the backend serves at /)
cd web && npm install && npm run build && cd ..

# Operator dashboard (produces frontend/dist/, served at /dashboard)
cd frontend && npm install && npm run build && cd ..

# Serve everything together
AUTH_USERNAME=sapphire AUTH_PASSWORD=<12+ chars> \
  backend/.venv/bin/python -m uvicorn backend.main:app --port 8099
```

## Marketing site rules (`web/`)
- **Every figure ships with the command that reproduces it.** All numbers live in
  `web/src/data/metrics.ts`, each with a `verify` one-liner rendered on the page.
  Re-measure with `./web/scripts/measure.sh` and update `MEASURED_SHA` / `MEASURED_AT`
  in the same commit. Never hand-edit a value.
- **Green means verified, and nothing else.** The `verified` colour token is owned solely by
  the `<Verified>` component. Do not use it decoratively — a green pixel is a claim.
- Sapphire is the only accent. Structure is hairlines; no glassmorphism, shadows, or
  radii past 2px.
- Prefer zero-JS primitives (`<details>` for the verify reveal, CSS for motion). The site
  must be fully readable with JavaScript disabled.
- All motion respects `prefers-reduced-motion`.

## Offline fallback
If `sapphirealpha.xyz` is unreachable from the current network/client, run the local fallback:
```bash
python local_dashboard_server.py --port 8080
open http://127.0.0.1:8080
```
It serves the existing `frontend/dist` bundle and mirrors `/api/v1/live` by
running the local telemetry collector directly. `/api/v1/moss`,
`/api/v1/widgets`, and `/api/fleet` return complete fail-closed offline stubs
so the UI renders cleanly without operator auth or invented observations.

## Deploy
The only supported manual release entrypoint is the clean-tree wrapper:
```bash
./deploy.sh
```
Do not invoke `gcloud builds submit` manually: the wrapper's clean-tree preflight is what
makes the embedded HEAD SHA truthful. The build also refuses a missing/invalid source
SHA. The Dockerfile uses `npm install` rather than
`npm ci` so the container build tolerates platform-specific optional dependencies in the
lockfile.

After an approved deploy, bind the public revision back to the intended source and both
frontend manifests:
```bash
python scripts/verify_deployment.py "$(git rev-parse HEAD)"
```
This is read-only. It also checks the public home, operator home, and calibration report
markers; a mismatch exits non-zero.

Custom domain: `sapphirealpha.xyz` is mapped to the `sapphire-alpha-dashboard` Cloud Run service in `us-central1`.

## Endpoints
- Public marketing site: `GET /`, `/architecture/`, `/trading/`, `/security/`, `/onchain/`, `/about/`
  - Anonymous **by design** — the front door must not sit behind Basic auth. Served only from
    `web/out`; no operator state reaches it. Asserted in `backend/tests/test_marketing_site.py`.
- Public SEO assets: `GET /robots.txt`, `GET /sitemap.xml`, `GET /opengraph-image`
  - Next.js writes the OG image **without a file extension**; `backend/main.py` maps it to
    `image/png` explicitly, or unfurlers drop the preview.
- Public build assets: `GET /_next/*` (fingerprinted, immutable cache)
- Public observatory: `GET /dashboard`, `GET /dashboard/*` — anonymous read-only (`auth_or_public`)
- Public: `GET /healthz`, `GET /api/health`
- Public build provenance: `GET /api/build` (source SHA, build ID, Cloud Run revision,
  and SHA-256 of both shipped HTML entrypoints; no private paths or host metadata)
- Signed ingest: `POST /api/v1/telemetry`, `POST /api/v1/moss/telemetry`
- Public compute projection: `GET /api/v1/live` (one undelayed numeric view for every reader)
- Public fixed vault taxonomy: `GET /api/v1/vault-map` (no private metadata); raw `GET /vault/rag-map` remains authenticated
- Narrow public/operator projections: `GET /api/v1/moss`, `GET /api/v1/transparency`
- Legacy reads with anonymous sanitizers: `GET /api/v1/status`, `GET /api/v1/widgets`, `GET /api/v1/tradingview/alerts`

## Widget data sources
The `/api/v1/widgets` endpoint aggregates:
- Trading gate state (`~/ops-state/rh-chain/gate.json`, `skin-book.json`, env overrides).
- Executor heartbeat (`~/ops-state/rh-chain/executor-heartbeat.json` or `DASHBOARD_EXECUTOR_HEARTBEAT`).
- Wallet / PnL (`~/ops-state/rh-chain/skin-book.json` or `DASHBOARD_SKIN_BOOK`).
- Telegram approval queue (`~/ops-state/telegram-bot/pending_queue.json`, `decisions.jsonl`).
- Recent signals (`~/ops-state/rh-chain/signals.json` or `DASHBOARD_SIGNALS_JSON`).
- Explicit multi-source research clips from `DASHBOARD_RESEARCH_CLIPS_JSON`. Unknown
  sources are rejected, candidates are capped at two clips per analyst, actual feed
  share is capped at 25%, and absence stays empty—there is no fabricated or
  single-source fallback.
- TradingView webhook status/log (`TV_WEBHOOK_URL`, `DASHBOARD_TV_LOG`).
- Business health probes (`GPU_GATEWAY_HEALTH_URL`, `REMOTE_GPU_GATEWAY_HEALTH_URL`, `OPS_SERVER_HEALTH_URL`).

The `/api/v1/tradingview/alerts` endpoint proxies recent alerts from the configured `TV_WEBHOOK_URL` receiver (`/alerts`).

The `/api/v1/transparency` endpoint serves the trade-rail explanation ledger (`~/ops-state/telegram-bot/explanations.jsonl`, schema 1 from telegram-bot `explain.py`): operators get the full whitelisted record; the public projection gets hashed ids and coarse USD bands (MOSS-pane masking precedent).

## Env overrides for Cloud Run
- `AUTH_USERNAME`, `AUTH_PASSWORD` (required, min 12 chars)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_TOKEN_FILE`, `TG_MINIAPP_ALLOWED_IDS`,
  `TG_MINIAPP_DECISION_URL` — private Mini App authentication and the bot decision deep link.
- `WALLET_ADDRESS` — full on-chain address (e.g. Robinhood Chain L2 wallet); dashboard masks it.
- `MAX_ORDER_USD`, `TELEGRAM_BOT_POLLING`
- `DASHBOARD_ARMED`, `DASHBOARD_MODE`, `DASHBOARD_FORCE_KILLSWITCH`
- `DASHBOARD_EXECUTOR_HEARTBEAT`, `DASHBOARD_SKIN_BOOK`, `DASHBOARD_SIGNALS_JSON`, `DASHBOARD_TV_LOG`
- `DASHBOARD_EXPLANATIONS_PATH` — override path to the explanations.jsonl ledger (Cloud Run has no Mac filesystem)
- `TV_WEBHOOK_STATUS`, `TV_WEBHOOK_URL`, `TV_LAST_PING`, `TV_PENDING_ALERTS`
  - `TV_WEBHOOK_URL` should be the **base origin** of the receiver (no path); the dashboard probes `<url>/webhook/health` and proxies `<url>/alerts`.
- `GPU_GATEWAY_HEALTH_URL`, `REMOTE_GPU_GATEWAY_HEALTH_URL`, `OPS_SERVER_HEALTH_URL`
- `DASHBOARD_RESEARCH_CLIPS_JSON`
- `TELEMETRY_STORE`, `TELEMETRY_INGEST_SECRET`, `MOSS_TELEMETRY_INGEST_SECRET`
- `TELEMETRY_FIRESTORE_DATABASE`, `MOSS_TELEMETRY_FIRESTORE_COLLECTION`

## Stable TradingView webhook hostname
The Mac Cloudflare Quick Tunnel URL rotates when the tunnel process restarts. For a persistent hostname:
1. **Tailscale Funnel** (preferred): enable at `https://login.tailscale.com/f/funnel?node=nV9oEWE1bM11CNTRL`, then set `TV_WEBHOOK_URL` to the Funnel origin.
2. **Cloudflare named tunnel**: create a tunnel, store its JSON credentials / token in `~/.config/sapphire-secrets/`, and run `cloudflared tunnel --config ...` as a LaunchAgent. Set `TV_WEBHOOK_URL` to the fixed origin.
3. Keep the Quick Tunnel as a fallback; run `./update-tv-webhook-url.sh` after any tunnel rotation to push the new origin into Cloud Run without a full rebuild.

## Health checks
The app exposes `GET /healthz` (public). Note: Cloud Run's Google Front End intercepts exact `/healthz` on `*.run.app` service URLs; use `/healthz/` or the custom domain apex for probing.

## Privacy rules
- No wallet identifier is exposed anonymously, including a masked one.
- Exact MOSS balances and masked identity are operator-only; the public view receives funding/freshness bands.
- No real names, exact public balances, chat IDs, or positions are exposed.
- No personal attribution or named research inputs appear in public copy, metadata,
  source-visible static content, or application bundles. Public research describes
  analytical lenses and evidence standards only; the identity and input hierarchy stay private.
- Never place a vault-derived map or knowledge export in `frontend/public`. The only
  public knowledge surface is the fixed, non-derived taxonomy from `/api/v1/vault-map`.
- Aggregate metrics and synthetic identifiers only.
- Telegram proposals/decisions are sanitized: PII keys (`chat_id`, `user_id`, `username`, etc.) are dropped before serialization.

## Knowledge base (one brain)
Shared vault: `~/Knowledge`. For deep research/context questions (never general coding):
1. Read `~/Knowledge/wiki/hot.md` (session cache), then `~/Knowledge/wiki/index.md`.
2. Then the relevant domain sub-index; only then drill into individual pages.
3. Retrieval: `python3 ~/Knowledge/wiki/wiki_query.py "question"` (lexical, cited) —
   add `--rag` (run with `~/Knowledge/7-Visual-Graphs/.venv/bin/python`) for semantic, cited retrieval.

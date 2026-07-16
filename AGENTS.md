# AGENTS.md — sapphire-alpha-dashboard

## Role
Public, privacy-preserving Mission Control for the Sapphire Alpha trading & business stack.

## Tech stack
- Backend: FastAPI + uvicorn (Python 3.11)
- Frontend: React 19 + Vite + TypeScript + Framer Motion
- Hosting: Cloud Run (Docker / Cloud Build deploy)
- Visual effects: WebGL starfield, animated grain, glassmorphism cards, reduced-motion support

## Local dev
```bash
cd backend
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest -q
cd ..
cd frontend
npm install && npm run build
```

## Deploy
Preferred: Cloud Build with explicit env substitution.
```bash
export AUTH_PASSWORD=$(security find-generic-password -s sapphire-alpha-dashboard -w)
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions=_AUTH_PASSWORD="$AUTH_PASSWORD" \
  --project=sapphire-479610 \
  --region=us-central1 \
  .
```

Alternative (local source deploy):
```bash
export AUTH_PASSWORD=$(security find-generic-password -s sapphire-alpha-dashboard -w)
./deploy.sh
```

The Dockerfile uses `npm install` rather than `npm ci` so the container build tolerates platform-specific optional dependencies in the lockfile.

Custom domain: `sapphirealpha.xyz` is mapped to the `sapphire-alpha-dashboard` Cloud Run service in `us-central1`.

## Endpoints
- Public: `GET /healthz`, `GET /api/health`
- Authenticated (`/api/v1/*`): `GET /status`, `GET /widgets`, `GET /tradingview/alerts`

## Widget data sources
The `/api/v1/widgets` endpoint aggregates:
- Trading gate state (`~/ops-state/rh-chain/gate.json`, `skin-book.json`, env overrides).
- Executor heartbeat (`~/ops-state/rh-chain/executor-heartbeat.json` or `DASHBOARD_EXECUTOR_HEARTBEAT`).
- Wallet / PnL (`~/ops-state/rh-chain/skin-book.json` or `DASHBOARD_SKIN_BOOK`).
- Telegram approval queue (`~/ops-state/telegram-bot/pending_queue.json`, `decisions.jsonl`).
- Recent signals (`~/ops-state/rh-chain/signals.json` or `DASHBOARD_SIGNALS_JSON`).
- DeFi Report clips (`~/Knowledge/3-Resources/Clippings/*.md`). With `TDR_PRO_LIVE=1`, Cloud Run falls back to fetching the public RSS feed directly.
- TradingView webhook status/log (`TV_WEBHOOK_URL`, `DASHBOARD_TV_LOG`).
- Business health probes (`GPU_GATEWAY_HEALTH_URL`, `REMOTE_GPU_GATEWAY_HEALTH_URL`, `OPS_SERVER_HEALTH_URL`).

The `/api/v1/tradingview/alerts` endpoint proxies recent alerts from the configured `TV_WEBHOOK_URL` receiver (`/alerts`).

## Env overrides for Cloud Run
- `AUTH_USERNAME`, `AUTH_PASSWORD` (required, min 12 chars)
- `WALLET_ADDRESS` — full on-chain address (e.g. Robinhood Chain L2 wallet); dashboard masks it.
- `MAX_ORDER_USD`, `TELEGRAM_BOT_POLLING`
- `DASHBOARD_ARMED`, `DASHBOARD_MODE`, `DASHBOARD_FORCE_KILLSWITCH`
- `DASHBOARD_EXECUTOR_HEARTBEAT`, `DASHBOARD_SKIN_BOOK`, `DASHBOARD_SIGNALS_JSON`, `DASHBOARD_TV_LOG`
- `TV_WEBHOOK_STATUS`, `TV_WEBHOOK_URL`, `TV_LAST_PING`, `TV_PENDING_ALERTS`
  - `TV_WEBHOOK_URL` should be the **base origin** of the receiver (no path); the dashboard probes `<url>/webhook/health` and proxies `<url>/alerts`.
- `GPU_GATEWAY_HEALTH_URL`, `REMOTE_GPU_GATEWAY_HEALTH_URL`, `OPS_SERVER_HEALTH_URL`
- `TDR_PRO_LIVE`

## Stable TradingView webhook hostname
The Mac Cloudflare Quick Tunnel URL rotates when the tunnel process restarts. For a persistent hostname:
1. **Tailscale Funnel** (preferred): enable at `https://login.tailscale.com/f/funnel?node=nV9oEWE1bM11CNTRL`, then set `TV_WEBHOOK_URL` to the Funnel origin.
2. **Cloudflare named tunnel**: create a tunnel, store its JSON credentials / token in `~/.config/sapphire-secrets/`, and run `cloudflared tunnel --config ...` as a LaunchAgent. Set `TV_WEBHOOK_URL` to the fixed origin.
3. Keep the Quick Tunnel as a fallback; update `TV_WEBHOOK_URL` and restart the Cloud Run revision after any rotation.

## Health checks
The app exposes `GET /healthz` (public). Note: Cloud Run's Google Front End intercepts exact `/healthz` on `*.run.app` service URLs; use `/healthz/` or the custom domain apex for probing.

## Privacy rules
- Wallet addresses are masked (`0xabcd…1234`).
- No real names, balances, chat IDs, or positions are exposed.
- Aggregate metrics and synthetic identifiers only.
- Telegram proposals/decisions are sanitized: PII keys (`chat_id`, `user_id`, `username`, etc.) are dropped before serialization.

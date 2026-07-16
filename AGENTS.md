# AGENTS.md — sapphire-alpha-dashboard

## Role
Public, privacy-preserving Mission Control for the Sapphire Alpha trading & business stack.

## Tech stack
- Backend: FastAPI + uvicorn (Python 3.11)
- Frontend: React 19 + Vite + TypeScript
- Hosting: Cloud Run (Docker source deploy)

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
```bash
export AUTH_PASSWORD=$(security find-generic-password -s sapphire-alpha-dashboard -w)
./deploy.sh
```

## Endpoints
- Public: `GET /healthz`, `GET /api/health`
- Authenticated (`/api/v1/*`): `GET /status`, `GET /widgets`

## Widget data sources
The `/api/v1/widgets` endpoint aggregates:
- Trading gate state (`~/ops-state/rh-chain/gate.json`, `skin-book.json`, env overrides).
- Executor heartbeat (`~/ops-state/rh-chain/executor-heartbeat.json` or `DASHBOARD_EXECUTOR_HEARTBEAT`).
- Wallet / PnL (`~/ops-state/rh-chain/skin-book.json` or `DASHBOARD_SKIN_BOOK`).
- Telegram approval queue (`~/ops-state/telegram-bot/pending_queue.json`, `decisions.jsonl`).
- Recent signals (`~/ops-state/rh-chain/signals.json` or `DASHBOARD_SIGNALS_JSON`).
- DeFi Report clips (`~/Knowledge/3-Resources/Clippings/*.md`).
- TradingView webhook status/log (`DASHBOARD_TV_LOG`).
- Business health probes (`GPU_GATEWAY_HEALTH_URL`, `REMOTE_GPU_GATEWAY_HEALTH_URL`, `OPS_SERVER_HEALTH_URL`).

## Env overrides for Cloud Run
- `AUTH_USERNAME`, `AUTH_PASSWORD` (required, min 12 chars)
- `WALLET_ADDRESS`, `MAX_ORDER_USD`, `TELEGRAM_BOT_POLLING`
- `DASHBOARD_ARMED`, `DASHBOARD_MODE`, `DASHBOARD_FORCE_KILLSWITCH`
- `DASHBOARD_EXECUTOR_HEARTBEAT`, `DASHBOARD_SKIN_BOOK`, `DASHBOARD_SIGNALS_JSON`, `DASHBOARD_TV_LOG`
- `TV_WEBHOOK_STATUS`, `TV_WEBHOOK_URL`, `TV_LAST_PING`, `TV_PENDING_ALERTS`
- `GPU_GATEWAY_HEALTH_URL`, `REMOTE_GPU_GATEWAY_HEALTH_URL`, `OPS_SERVER_HEALTH_URL`
- `TDR_PRO_LIVE`

## Health checks
The app exposes `GET /healthz` (public). Note: Cloud Run's Google Front End intercepts exact `/healthz` on `*.run.app` service URLs; use `/healthz/` or the custom domain apex for probing.

## Privacy rules
- Wallet addresses are masked (`0xabcd…1234`).
- No real names, balances, chat IDs, or positions are exposed.
- Aggregate metrics and synthetic identifiers only.
- Telegram proposals/decisions are sanitized: PII keys (`chat_id`, `user_id`, `username`, etc.) are dropped before serialization.

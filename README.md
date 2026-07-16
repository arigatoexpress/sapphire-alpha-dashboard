# Sapphire Alpha Dashboard

Mission Control for the Sapphire trading + ops stack — a unified, animated, privacy-preserving control plane running on Google Cloud Run at **[sapphirealpha.xyz](https://sapphirealpha.xyz)**.

FastAPI backend + React/Vite frontend, shipped as a single container.

## What's new (2026-07)

- **Mission Control UI** — full artistic refactor: starfield canvas, glass status tiles, live alert stream, cinematic grain, live clock.
- **TradingView alerts pipeline** — live webhook probe + durable alert log widget (`/api/v1/tradingview/alerts`), with a helper script to rotate the webhook URL.
- **TDR Pro clips** — backend fetches The DeFi Report Pro RSS directly from Cloud Run (`TDR_PRO_LIVE=1`); no baked-in data blobs.
- **Knowledge-vault RAG map** — auth-gated interactive map at `/vault/rag-map`.
- **Public read-only mode** — anonymous visitors get a sanitized, read-only main page; operator detail (queues, heartbeats, vault views) stays behind auth.
- **Deploy hardening** — `deploy.sh` now *merges* env vars on redeploy instead of wiping them; cross-platform image builds via `cloudbuild.yaml`.
- **CI** — backend pytest + frontend build on every push (`.github/workflows/ci.yml`).

## Widgets

The main page composes live status tiles served by `/api/v1/widgets`:

| Widget | What it shows |
|---|---|
| Gate | Trading-gate armed/disarmed state |
| Wallet | Masked wallet status (addresses always redacted) |
| Telegram queue | Pending decision proposals (sanitized) |
| Signals | Recent strategy signals |
| TradingView | Webhook liveness probe + recent alerts |
| TDR clips | Latest The DeFi Report Pro items |
| Business health | Upstream service health probes |
| System | Executor heartbeat + system health |

## Access model

- **Anonymous (public read-only):** sanitized main page — aggregate metrics, masked identifiers, no operational controls.
- **Authenticated (HTTP Basic):** full widget detail plus `/vault/rag-map`.
- `/healthz` and `/api/health` are public liveness endpoints.

## Structure

- `backend/` — FastAPI service: auth, widget aggregation, sanitizers, security-header + path-traversal middleware
- `frontend/` — React + Vite dark animated UI
- `deploy.sh` — Cloud Run deploy (env-merge mode)
- `cloudbuild.yaml` / `Dockerfile` — container build
- `update-tv-webhook-url.sh` — rotate the TradingView webhook target env var

## Local development

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
AUTH_USERNAME=sapphire AUTH_PASSWORD=change-me-now python -m uvicorn main:app --reload --port 8080
```

```bash
cd frontend
npm install
npm run dev
```

## Tests

```bash
cd backend && pytest
cd frontend && npm run build
```

## Deploy

```bash
./deploy.sh
```

Reads secrets from the local keychain; merges (never clobbers) existing Cloud Run env vars.

## Privacy

This repo and the deployed dashboard are privacy-preserving by construction:

- Wallet addresses are masked (`0xabcd...1234`); never shown in full.
- No real names, balances, chat IDs, or account identifiers are exposed.
- Aggregate metrics and synthetic identifiers only.
- Anonymous traffic sees a further-sanitized read-only view.

# AGENTS.md — sapphire-alpha-dashboard

## Role
Public, privacy-preserving control plane for the Sapphire Alpha trading & business stack.

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
export AUTH_PASSWORD=<strong secret>
./deploy.sh
```

## Health checks
The app exposes `GET /healthz` (public). Note: Cloud Run's Google Front End intercepts exact `/healthz` on `*.run.app` service URLs; use `/healthz/` or the custom domain apex for probing.

## Privacy rules
- Wallet addresses are masked (`0xabcd…1234`).
- No real names, balances, chat IDs, or positions are exposed.
- Aggregate metrics and synthetic identifiers only.

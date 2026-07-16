# Sapphire Alpha Dashboard

Unified, animated, privacy-preserving trading & business control plane.

## Structure

- `backend/` — FastAPI service with HTTP Basic Auth and `/healthz`
- `frontend/` — React + Vite dark animated UI

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
cd backend
pytest
```

```bash
cd frontend
npm run build
```

## Deploy

```bash
export AUTH_PASSWORD=$(security find-generic-password -s sapphire-alpha-dashboard -w)
./deploy.sh
```

## Privacy

- Wallet addresses are masked (`0xabcd...1234`).
- No real names, balances, or chat IDs are exposed.
- Aggregate metrics and synthetic identifiers only.

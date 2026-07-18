# Sapphire Alpha Observatory

The public, read-only front door for the Sapphire system: a professional live view of distributed compute, agent activity, Robinhood Chain research, and verified system events at **[sapphirealpha.xyz](https://sapphirealpha.xyz)**.

FastAPI + React/Vite, shipped as one Cloud Run container. The application has no trading or infrastructure actuation routes.

## Signal Loom architecture

```text
home-mesh raw observations
  RH Chain, MOSS/MegaETH, Windows GPU, agent health, knowledge cycles
       |
       v
local semantic projector
  aggregate -> allowlist -> validate -> HMAC sign
       |
       v
Cloud Run signed ingest -> Firestore latest + bounded history
       |
       +--> delayed public projection
       +--> authenticated operator projection
       v
Signal Loom + agents + research + evidence ledger
```

The animation is data-backed. Link width and speed come from observed activity; color comes from signal class and health. A quiet link does not animate. Missing sources render `not observed`, `warming`, `stale`, or `offline`—never synthetic market activity.

## Privacy boundary

Public telemetry may contain semantic roles, status and load bands, bucketed freshness/latency/activity, bounded agent presence, research feed state, paper-strategy count, decision-gate class, and execution mode.

It rejects hostnames, addresses, ports, endpoints, paths, credentials, prompts, wallet/account material, balances, positions, orders, raw errors, and unknown fields. The local projector and server both enforce the boundary.

MOSS uses a separate, stricter lane so the general Signal Loom stays wallet-blind.
Authenticated operators may see a masked identity and exact decimal-string balances;
the anonymous projection withholds identity, bands USDm capital, reduces ETH to
present/empty, and exposes freshness rather than exact block height.

## APIs

- `POST /api/v1/telemetry` — HMAC-signed, replay-protected semantic snapshots, 64 KiB maximum
- `GET /api/v1/live` — delayed aggregate public view or bounded authenticated operator view
- `POST /api/v1/moss/telemetry` — separately signed, masked MOSS/MegaETH observation
- `GET /api/v1/moss` — banded anonymous asset state or exact authenticated operator view
- `GET /api/health` — public service liveness
- Legacy `/api/v1/widgets` and `/api/fleet` remain during migration, but the observatory does not treat their deploy-time state as live truth.

## Local development

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
AUTH_USERNAME=sapphire AUTH_PASSWORD=change-me-now \
  TELEMETRY_INGEST_SECRET=replace-with-32-plus-random-characters \
  MOSS_TELEMETRY_INGEST_SECRET=replace-with-a-distinct-32-plus-character-secret \
  PUBLIC_READ_ONLY=1 PUBLIC_TELEMETRY_DELAY_SECONDS=0 \
  python -m uvicorn main:app --reload --port 8080
```

In another terminal, inspect the safe projection or push it to the local server:

```bash
PYTHONPATH=backend:. python -m telemetry.collector

SAPPHIRE_TELEMETRY_ENDPOINT=http://127.0.0.1:8080/api/v1/telemetry \
TELEMETRY_INGEST_SECRET=replace-with-32-plus-random-characters \
PYTHONPATH=backend:. python -m telemetry.collector --push

# Once the private MOSS observatory has produced its masked local snapshot:
PYTHONPATH=backend:. python -m telemetry.moss_collector

SAPPHIRE_MOSS_TELEMETRY_ENDPOINT=http://127.0.0.1:8080/api/v1/moss/telemetry \
MOSS_TELEMETRY_INGEST_SECRET=replace-with-a-distinct-32-plus-character-secret \
PYTHONPATH=backend:. python -m telemetry.moss_collector --push
```

Optional local-only probe variables (`SAPPHIRE_EDGE_PROBE`, `SAPPHIRE_COMPUTE_PROBE`, `SAPPHIRE_MARKETS_PROBE`, `SAPPHIRE_ARCHIVE_PROBE`) add measured RTT to the corresponding semantic link. Probe addresses are never included in the snapshot; missing measurements remain `not observed`.

```bash
cd frontend
npm ci
npm run build
```

## Verification

```bash
cd backend && PYTHONPATH=.. pytest -q
cd frontend && npm run build
```

Golden tests cover signature validation, timestamp skew, nonce replay, sequence ordering, schema bounds, non-finite numbers, public projection, sensitive-field rejection, missing-source honesty, local-projector fidelity, and the MOSS operator/public privacy split.

## Deployment gate

Production uses Firestore and Secret Manager through the least-privileged `sapphire-dashboard-sa` service account. `infra/bootstrap-telemetry.sh` is a one-time IAM/secret bootstrap and is intentionally never called by CI. Creating the telemetry secret, changing IAM, deploying, and activating the home publisher are explicit operator gates.

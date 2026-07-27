# Sapphire Alpha Observatory

Two surfaces at **[sapphirealpha.xyz](https://sapphirealpha.xyz)**, shipped as one Cloud Run container:

| Path | Surface | Access |
| --- | --- | --- |
| `/` | **Evidence Observatory** (`web/`) — the research method, published evidence, architecture, and public operating boundary | Anonymous |
| `/dashboard` | **Decision Observatory** (`frontend/`) — current exceptions, changes, authority, and source-level evidence | Anonymous |

FastAPI + a statically exported Next.js site + a React/Vite SPA. The application has no trading or infrastructure actuation routes.

## The marketing site

Its argument is that its claims are checkable, so it is built to make that literal: every
figure carries the shell one-liner that reproduces it, rendered on the page next to the
number. Figures live in `web/src/data/metrics.ts` and are produced by:

```bash
./web/scripts/measure.sh ~/Code/Sapphire
```

Two rules keep it honest:

- **Numbers are transcribed, never estimated.** Re-run the script and update `MEASURED_SHA`
  and `MEASURED_AT` in the same commit as any value that moved.
- **Green means verified.** The verified colour token belongs to the `<Verified>` component
  alone, so a green pixel always denotes a checked claim rather than decoration.

The site is a static export (`output: 'export'`) — prerendered HTML with no Next.js server,
fully readable with JavaScript disabled, served straight from the FastAPI container.

## Evidence flow

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
       +--> one undelayed compute projection
       +--> narrowly sanitized capital and legacy projections
       v
Evidence Horizon + agents + research + evidence ledger
```

Each source retains its own freshness and authority. Missing sources render `not observed`,
`warming`, `stale`, or `offline`—never synthetic market activity or implied permission.

## Privacy boundary

Public compute telemetry contains semantic roles, status, measured load, freshness and
latency, and measured link activity where the collector can observe it. An unobservable
rate is `null`, never a made-up zero. Agent presence, research feed state,
paper-strategy count, decision-gate class, and execution mode are also public.

It rejects hostnames, addresses, ports, endpoints, paths, credentials, prompts, wallet/account material, balances, positions, orders, raw errors, and unknown fields. The local projector and server both enforce the boundary.

MOSS uses a separate, stricter lane so the general Signal Routes view stays wallet-blind.
Authenticated operators may see a masked identity and exact decimal-string balances;
the anonymous projection withholds identity, bands USDm capital, reduces ETH to
present/empty, and exposes freshness rather than exact block height.

## APIs

- `POST /api/v1/telemetry` — HMAC-signed, replay-protected semantic snapshots, 64 KiB maximum
- `GET /api/v1/live` — anonymous, undelayed compute telemetry with measured numbers
- `POST /api/v1/moss/telemetry` — separately signed, masked MOSS/MegaETH observation
- `GET /api/v1/moss` — banded anonymous asset state or exact authenticated operator view
- `GET /api/v1/vault-map` — fixed public topic taxonomy; no titles, paths, counts, mount state, or note content
- `GET /api/health` — public service liveness
- `GET /api/build` — source SHA, Cloud Build ID, Cloud Run revision, and deterministic
  manifests for both shipped frontend trees
- Raw `GET /vault/rag-map` remains authenticated. `/api/v1/widgets` supplies
  the observatory's anonymous evidence and system watchboard; it remains
  advisory and cannot grant execution authority. `/api/fleet` remains a
  sanitized coordination view.

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

Two optional local-only probe variables match the RTTs the Mac collector can
actually measure: `SAPPHIRE_EDGE_PROBE` for public edge → orchestration and
`SAPPHIRE_GPU_GATEWAY_PROBE` for orchestration → the first healthy compute tier.
Probe addresses are never included in the snapshot. The remaining semantic
links have no addressable RTT source and remain `not observed`; feed timestamp
lag is freshness, not network latency.

```bash
cd frontend
npm ci
npm run build
```

For the fully local, fail-closed fallback:

```bash
python local_dashboard_server.py --port 8080
open http://127.0.0.1:8080/dashboard
```

The fallback runs the local telemetry collector and serves explicit offline
projections for assets, evidence/system watch, and fleet coordination. It never
turns an unavailable upstream into an observed zero or an executable state.

## Verification

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run typecheck:shared
npm --prefix frontend run build
npm --prefix web test
npm --prefix web run build
```

Golden tests cover signature validation, timestamp skew, nonce replay, sequence
ordering, schema bounds, non-finite numbers, sensitive-field rejection,
measurement provenance, missing-source honesty, local-projector fidelity, the
sanitized vault map, narration, responsive non-overlap, and the MOSS
operator/public privacy split.

An approved release uses one immutable build path:

```bash
./deploy.sh
python scripts/verify_deployment.py "$(git rev-parse HEAD)"
```

The wrapper refuses a dirty tree or invalid source SHA, delegates to the canonical Cloud
Build config, and tags the image with the Cloud Build ID. Do not bypass its clean-tree
preflight with a raw submit command. The verifier is read-only and checks the deployed source, runtime revision, both
frontend manifests, and representative public routes.

## Deployment gate

Production uses Firestore and Secret Manager through the least-privileged `sapphire-dashboard-sa` service account. `infra/bootstrap-telemetry.sh` is a one-time IAM/secret bootstrap and is intentionally never called by CI. Creating the telemetry secret, changing IAM, deploying, and activating the home publisher are explicit operator gates.

## IPv6 accessibility note

`sapphirealpha.xyz` publishes both IPv4 and IPv6 (AAAA) records. Some networks cannot route the IPv6 endpoints, which makes the site appear unreachable in browsers that prefer IPv6 even though IPv4 works. If the site does not load, force IPv4:

```bash
curl -4 https://sapphirealpha.xyz/api/v1/live
```

or disable IPv6 for the domain in the browser/OS. The service itself is healthy on IPv4.

## Merged Mac + Windows telemetry

`telemetry/merged_collector.py` combines the Mac fleet snapshot with the Windows workhorse snapshot (over SSH) and pushes a single signed snapshot so both sources appear on the dashboard at once. The Mac collector and Windows collector individually overwrite the single latest snapshot; use the merged collector for the live demo loop:

```bash
SAPPHIRE_TELEMETRY_ENDPOINT=https://sapphirealpha.xyz/api/v1/telemetry \
TELEMETRY_INGEST_SECRET=... \
python3 telemetry/merged_collector.py --push
```

### Scheduled publisher

Without a scheduled publisher the live feed goes stale and the site advertises a
days-old snapshot. `telemetry/run_publisher.sh` sources the ingest secret from
`~/.sapphire/sapphirealpha-telemetry.env` (never from the plist) and pushes a
merged snapshot; the LaunchAgent runs it every 5 minutes.

The publisher never retries an unknown rate as zero. During a producer/backend
schema transition, an older backend may reject the honest nullable payload; in
that case the prior accepted snapshot remains visible until the backend is
upgraded rather than being replaced with invented quiet traffic.

```bash
cp infra/com.sapphire.alpha-telemetry-publisher.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.sapphire.alpha-telemetry-publisher.plist
launchctl list | grep alpha-telemetry-publisher      # expect exit status 0

tail -f ~/autonomy-status/logs/alpha-telemetry-publisher.log   # {"accepted": true, ...}
```

To stop publishing: `launchctl unload ~/Library/LaunchAgents/com.sapphire.alpha-telemetry-publisher.plist`.

If the Windows host is asleep or off-network the SSH leg is skipped and the
snapshot degrades to Mac-only rather than failing.

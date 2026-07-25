# Sapphire Alpha Observatory

Two surfaces at **[sapphirealpha.xyz](https://sapphirealpha.xyz)**, shipped as one Cloud Run container:

| Path | Surface | Access |
| --- | --- | --- |
| `/` | **Marketing site** (`web/`) — the front door: architecture, trading, security, on-chain, about | Anonymous |
| `/dashboard` | **Observatory** (`frontend/`) — live view of distributed compute, agent activity, Robinhood Chain research, and verified system events | Auth-gated |

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
PYTHONPATH=backend:. pytest -q
cd frontend && npm run build
```

Golden tests cover signature validation, timestamp skew, nonce replay, sequence ordering, schema bounds, non-finite numbers, public projection, sensitive-field rejection, missing-source honesty, local-projector fidelity, and the MOSS operator/public privacy split.

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

```bash
cp infra/com.sapphire.alpha-telemetry-publisher.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.sapphire.alpha-telemetry-publisher.plist
launchctl list | grep alpha-telemetry-publisher      # expect exit status 0

tail -f ~/autonomy-status/logs/alpha-telemetry-publisher.log   # {"accepted": true, ...}
```

To stop publishing: `launchctl unload ~/Library/LaunchAgents/com.sapphire.alpha-telemetry-publisher.plist`.

If the Windows host is asleep or off-network the SSH leg is skipped and the
snapshot degrades to Mac-only rather than failing.

#!/usr/bin/env bash
# Export the dashboard-safe fleet snapshot and publish it to the durable lane.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${SAPPHIRE_TELEMETRY_ENV:-$HOME/.sapphire/sapphirealpha-telemetry.env}"
FLEET_LEASE_BIN="${FLEET_LEASE_BIN:-$HOME/bin/fleet-lease}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "$(date -u +%FT%TZ) FATAL telemetry env file not found: $ENV_FILE" >&2
    exit 1
fi
if [[ ! -x "$FLEET_LEASE_BIN" ]]; then
    echo "$(date -u +%FT%TZ) FATAL fleet-lease unavailable" >&2
    exit 1
fi

# shellcheck source=/dev/null
set -a && . "$ENV_FILE" && set +a

: "${TELEMETRY_INGEST_SECRET:?TELEMETRY_INGEST_SECRET is required}"
export SAPPHIRE_FLEET_TELEMETRY_ENDPOINT="${SAPPHIRE_FLEET_TELEMETRY_ENDPOINT:-https://sapphirealpha.xyz/api/v1/fleet/telemetry}"

PYTHON="$REPO_DIR/backend/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"

FLEET_TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sapphire-fleet.XXXXXX")"
trap 'rm -rf "$FLEET_TMP_DIR"' EXIT
SNAPSHOT="$FLEET_TMP_DIR/fleet.json"

"$FLEET_LEASE_BIN" export --sanitized --out "$SNAPSHOT" >/dev/null
"$PYTHON" "$REPO_DIR/telemetry/fleet_collector.py" \
    --state "$SNAPSHOT" \
    --push

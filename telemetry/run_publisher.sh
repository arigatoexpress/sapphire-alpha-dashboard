#!/usr/bin/env bash
# Publish a merged Mac + Windows telemetry snapshot to sapphirealpha.xyz.
#
# Invoked by the com.sapphire.alpha-telemetry-publisher LaunchAgent every 60
# seconds (StartInterval in infra/com.sapphire.alpha-telemetry-publisher.plist,
# which must stay well under live_telemetry.DEFAULT_STALE_AFTER_SECONDS).
# The ingest secret is sourced from ~/.sapphire/ and is deliberately
# NOT stored in the plist, so it never lands in launchctl output or a backup.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${SAPPHIRE_TELEMETRY_ENV:-$HOME/.sapphire/sapphirealpha-telemetry.env}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "$(date -u +%FT%TZ) FATAL telemetry env file not found: $ENV_FILE" >&2
    exit 1
fi

# shellcheck source=/dev/null
set -a && . "$ENV_FILE" && set +a

: "${TELEMETRY_INGEST_SECRET:?TELEMETRY_INGEST_SECRET is required}"
: "${SAPPHIRE_TELEMETRY_ENDPOINT:?SAPPHIRE_TELEMETRY_ENDPOINT is required}"

# Prefer the backend venv (has the collector's deps); fall back to system python.
PYTHON="$REPO_DIR/backend/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"

# The Windows leg goes over SSH and may be unreachable (host asleep, off-net).
# merged_collector degrades to Mac-only in that case; a non-zero exit here means
# the push itself failed, which is what we want surfaced in the error log.
exec "$PYTHON" "$REPO_DIR/telemetry/merged_collector.py" --push

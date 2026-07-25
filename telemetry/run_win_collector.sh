#!/usr/bin/env bash
# Run the Windows workhorse telemetry publisher from the Mac.
# Sources ~/.sapphire/sapphirealpha-telemetry.env and invokes the collector
# already placed on the Windows node at C:\Users\aribs\.sapphire\win_collector.py.
set -euo pipefail

ENV_FILE="${1:-$HOME/.sapphire/sapphirealpha-telemetry.env}"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "Telemetry env file not found: $ENV_FILE" >&2
    exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

: "${TELEMETRY_INGEST_SECRET:?TELEMETRY_INGEST_SECRET is required}"

WIN_HOST="${WIN_HOST:-win}"
WIN_SCRIPT="${WIN_SCRIPT:-C:\\Users\\aribs\\.sapphire\\win_collector.py}"
ENDPOINT="${SAPPHIRE_TELEMETRY_ENDPOINT:-https://sapphirealpha.xyz/api/v1/telemetry}"

# Pass secret via PowerShell environment; nothing is logged.
ssh "$WIN_HOST" "powershell -Command \"\$env:TELEMETRY_INGEST_SECRET='$TELEMETRY_INGEST_SECRET'; \$env:SAPPHIRE_TELEMETRY_ENDPOINT='$ENDPOINT'; python '$WIN_SCRIPT' --push\""

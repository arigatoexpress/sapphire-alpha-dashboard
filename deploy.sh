#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ID="${PROJECT_ID:-sapphire-479610}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sapphire-alpha-dashboard}"

echo "Deploying ${SERVICE_NAME} to Cloud Run..."
cd "${SERVICE_DIR}"

if [[ -z "${AUTH_PASSWORD:-}" ]]; then
  echo "ERROR: AUTH_PASSWORD must be set" >&2
  exit 1
fi

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --allow-unauthenticated \
  --update-env-vars "AUTH_USERNAME=${AUTH_USERNAME:-sapphire}" \
  --update-env-vars "AUTH_PASSWORD=${AUTH_PASSWORD}" \
  --update-env-vars "WALLET_ADDRESS=${WALLET_ADDRESS:-}" \
  --update-env-vars "MAX_ORDER_USD=${MAX_ORDER_USD:-25}" \
  --update-env-vars "TELEGRAM_BOT_POLLING=${TELEGRAM_BOT_POLLING:-true}" \
  --update-env-vars "TV_WEBHOOK_STATUS=${TV_WEBHOOK_STATUS:-standby}" \
  --update-env-vars "TV_WEBHOOK_URL=${TV_WEBHOOK_URL:-not configured}" \
  --update-env-vars "TDR_PRO_LIVE=${TDR_PRO_LIVE:-0}" \
  --update-env-vars "DASHBOARD_ARMED=${DASHBOARD_ARMED:-false}" \
  --update-env-vars "DASHBOARD_MODE=${DASHBOARD_MODE:-telegram}" \
  --update-env-vars "DASHBOARD_FORCE_KILLSWITCH=${DASHBOARD_FORCE_KILLSWITCH:-false}" \
  --update-env-vars "DASHBOARD_EXECUTOR_HEARTBEAT=${DASHBOARD_EXECUTOR_HEARTBEAT:-}" \
  --update-env-vars "DASHBOARD_SIGNALS_JSON=${DASHBOARD_SIGNALS_JSON:-}"

echo
echo "Service URL:"
gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format 'value(status.url)'

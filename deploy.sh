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
  --set-env-vars "AUTH_USERNAME=${AUTH_USERNAME:-sapphire}" \
  --set-env-vars "AUTH_PASSWORD=${AUTH_PASSWORD}" \
  --set-env-vars "WALLET_ADDRESS=${WALLET_ADDRESS:-}" \
  --set-env-vars "MAX_ORDER_USD=${MAX_ORDER_USD:-25}" \
  --set-env-vars "TELEGRAM_BOT_POLLING=${TELEGRAM_BOT_POLLING:-true}" \
  --set-env-vars "TV_WEBHOOK_STATUS=${TV_WEBHOOK_STATUS:-standby}" \
  --set-env-vars "TV_WEBHOOK_URL=${TV_WEBHOOK_URL:-not configured}" \
  --set-env-vars "TDR_PRO_LIVE=${TDR_PRO_LIVE:-0}" \
  --set-env-vars "DASHBOARD_ARMED=${DASHBOARD_ARMED:-false}" \
  --set-env-vars "DASHBOARD_MODE=${DASHBOARD_MODE:-telegram}" \
  --set-env-vars "DASHBOARD_FORCE_KILLSWITCH=${DASHBOARD_FORCE_KILLSWITCH:-false}" \
  --set-env-vars "DASHBOARD_EXECUTOR_HEARTBEAT=${DASHBOARD_EXECUTOR_HEARTBEAT:-}" \
  --set-env-vars "DASHBOARD_SIGNALS_JSON=${DASHBOARD_SIGNALS_JSON:-}"

echo
echo "Service URL:"
gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format 'value(status.url)'

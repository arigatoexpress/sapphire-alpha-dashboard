#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ID="${PROJECT_ID:-sapphire-479610}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sapphire-alpha-dashboard}"
TUNNEL_URL_FILE="${TUNNEL_URL_FILE:-$HOME/Code/Sapphire/data/webhook/tunnel_url.txt}"

if [[ ! -f "$TUNNEL_URL_FILE" ]]; then
  echo "ERROR: tunnel URL file not found: $TUNNEL_URL_FILE" >&2
  exit 1
fi

TUNNEL_URL="$(tr -d '[:space:]' < "$TUNNEL_URL_FILE")"
if [[ -z "$TUNNEL_URL" ]]; then
  echo "ERROR: tunnel URL file is empty" >&2
  exit 1
fi

echo "Updating $SERVICE_NAME TV_WEBHOOK_URL to $TUNNEL_URL ..."
gcloud run services update "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --update-env-vars "TV_WEBHOOK_URL=$TUNNEL_URL"

echo "Done. New URL: $TUNNEL_URL"

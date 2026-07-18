#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ID="${PROJECT_ID:-sapphire-479610}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sapphire-alpha-dashboard}"

echo "Deploying ${SERVICE_NAME} to Cloud Run..."
cd "${SERVICE_DIR}"

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --allow-unauthenticated \
  --service-account="sapphire-dashboard-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --update-env-vars "AUTH_USERNAME=${AUTH_USERNAME:-sapphire}" \
  --update-env-vars "PUBLIC_READ_ONLY=1,PUBLIC_TELEMETRY_DELAY_SECONDS=15,TELEMETRY_STORE=firestore,TELEMETRY_FIRESTORE_COLLECTION=sapphire_live_v1" \
  --set-secrets "AUTH_PASSWORD=SAPPHIRE_AUTH_PASSWORD:latest,TELEMETRY_INGEST_SECRET=SAPPHIRE_TELEMETRY_INGEST_SECRET:latest"

echo
echo "Service URL:"
gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format 'value(status.url)'

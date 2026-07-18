#!/usr/bin/env bash
set -euo pipefail

# One-time, explicitly gated bootstrap. This script intentionally does not run
# as part of deploy or CI because it changes IAM and secret infrastructure.
PROJECT_ID="${PROJECT_ID:-sapphire-479610}"
DASHBOARD_SA="sapphire-dashboard-sa@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud secrets create SAPPHIRE_TELEMETRY_INGEST_SECRET \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${DASHBOARD_SA}" \
  --role=roles/datastore.user

for secret_name in SAPPHIRE_AUTH_PASSWORD SAPPHIRE_TELEMETRY_INGEST_SECRET; do
  gcloud secrets add-iam-policy-binding "${secret_name}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${DASHBOARD_SA}" \
    --role=roles/secretmanager.secretAccessor
done

echo "Add a random 32+ byte secret version through an approved operator flow."

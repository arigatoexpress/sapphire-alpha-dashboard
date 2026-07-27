#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ID="${PROJECT_ID:-sapphire-479610}"
REGION="us-central1"
SERVICE_NAME="sapphire-alpha-dashboard"
BUILD_SHA="$(git -C "${SERVICE_DIR}" rev-parse HEAD)"

if [[ -n "$(git -C "${SERVICE_DIR}" status --porcelain)" ]]; then
  echo "Refusing source deploy from a dirty worktree." >&2
  exit 1
fi

echo "Submitting immutable ${SERVICE_NAME} build ${BUILD_SHA}..."
cd "${SERVICE_DIR}"

gcloud builds submit . \
  --config cloudbuild.yaml \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --substitutions="_BUILD_SHA=${BUILD_SHA}"

echo
echo "Service URL:"
gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format 'value(status.url)'

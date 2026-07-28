#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SERVICE_DIR
readonly PROJECT_ID="sapphire-479610"
readonly REGION="us-central1"

if [[ "$#" -ne 2 ]]; then
  echo "usage: deploy.sh ACTION_DESCRIPTOR ACTION_DESCRIPTOR_SHA256" >&2
  exit 2
fi

readonly ACTION_DESCRIPTOR="$1"
readonly ACTION_DESCRIPTOR_SHA256="$2"
BUILD_SHA="$(git -C "${SERVICE_DIR}" rev-parse HEAD)"
readonly BUILD_SHA

if [[ -n "$(git -C "${SERVICE_DIR}" status --porcelain)" ]]; then
  echo "Refusing source deploy from a dirty worktree." >&2
  exit 1
fi

EXPECTED_SHA="$(
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source"]["commit_sha"])' \
    "${ACTION_DESCRIPTOR}"
)"
readonly EXPECTED_SHA
if [[ "${BUILD_SHA}" != "${EXPECTED_SHA}" ]]; then
  echo "Refusing source deploy from an unbound commit." >&2
  exit 1
fi

python3 "${SERVICE_DIR}/scripts/deploy_contract.py" local-preflight \
  --descriptor "${ACTION_DESCRIPTOR}" \
  --descriptor-sha256 "${ACTION_DESCRIPTOR_SHA256}"

TEMP_DIR="$(mktemp -d)"
readonly TEMP_DIR
trap 'rm -rf "${TEMP_DIR}"' EXIT
readonly RENDERED_CONFIG="${TEMP_DIR}/cloudbuild.json"

python3 "${SERVICE_DIR}/scripts/deploy_contract.py" render-cloudbuild \
  --descriptor "${ACTION_DESCRIPTOR}" \
  --descriptor-sha256 "${ACTION_DESCRIPTOR_SHA256}" \
  --template "${SERVICE_DIR}/cloudbuild.yaml" \
  --output "${RENDERED_CONFIG}"

# --no-source is deliberate: the rendered config already binds an existing
# bucket/object/generation. gcloud must not stage bytes or create a bucket.
BUILD_ID="$(
  gcloud builds submit \
    --no-source \
    --config="${RENDERED_CONFIG}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format='value(id)' \
    --quiet
)"
readonly BUILD_ID

python3 "${SERVICE_DIR}/scripts/deploy_contract.py" verify-build \
  --descriptor-zlib-b64 "$(
    python3 -c 'import base64,sys,zlib; print(base64.b64encode(zlib.compress(open(sys.argv[1], "rb").read(), 9)).decode())' \
      "${ACTION_DESCRIPTOR}"
  )" \
  --descriptor-sha256 "${ACTION_DESCRIPTOR_SHA256}" \
  --build-id "${BUILD_ID}" \
  --require-success

python3 "${SERVICE_DIR}/scripts/deploy_contract.py" postdeploy \
  --descriptor-zlib-b64 "$(
    python3 -c 'import base64,sys,zlib; print(base64.b64encode(zlib.compress(open(sys.argv[1], "rb").read(), 9)).decode())' \
      "${ACTION_DESCRIPTOR}"
  )" \
  --descriptor-sha256 "${ACTION_DESCRIPTOR_SHA256}" \
  --build-id "${BUILD_ID}"

python3 "${SERVICE_DIR}/scripts/verify_deployment.py" \
  "${BUILD_SHA}" \
  --base-url "https://sapphire-alpha-dashboard-s77j6bxyra-uc.a.run.app"

echo "Release and read-only postcheck completed."

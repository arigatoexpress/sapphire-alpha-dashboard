#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SERVICE_DIR

if [[ "$#" -ne 2 ]]; then
  echo "usage: deploy.sh ACTION_DESCRIPTOR ACTION_DESCRIPTOR_SHA256" >&2
  exit 2
fi

if [[ -z "${SAPPHIRE_TRUSTED_WRAPPER_SHA256:-}" ]] ||
   [[ -z "${SAPPHIRE_TRUSTED_LAUNCHER_SHA256:-}" ]] ||
   [[ -z "${SAPPHIRE_TRUSTED_PYTHON_SHA256:-}" ]] ||
   [[ -z "${SAPPHIRE_TRUSTED_GUARD_SHA256:-}" ]] ||
   [[ -z "${SAPPHIRE_TRUSTED_GIT_SHA256:-}" ]] ||
   [[ -z "${SAPPHIRE_TRUSTED_GCLOUD_SHA256:-}" ]] ||
   [[ -z "${SAPPHIRE_TRUSTED_RENDERED_CONFIG_SHA256:-}" ]]; then
  echo "Refusing release without the externally pinned execution closure." >&2
  exit 1
fi

# One explicit approval invokes one externally hash-pinned launcher. All source,
# bucket, build, provider-CAS, and readback checks happen inside that closure.
exec python3 "${SERVICE_DIR}/scripts/trusted_release.py" run \
  --descriptor "$1" \
  --descriptor-sha256 "$2"

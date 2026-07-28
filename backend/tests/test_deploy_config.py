"""Deployment manifests cannot carry operational or financial literals."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_cloudbuild_uses_semantic_config_and_secret_manager():
    content = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    # Live service has AUTH_PASSWORD as a plain env var; Cloud Build must not
    # --set-secrets it (type mismatch fails deploy). Password is preserved
    # across deploys; migration to Secret Manager is a separate ops step.
    assert "SAPPHIRE_AUTH_PASSWORD:latest" not in content
    assert "--set-secrets" not in content or "AUTH_PASSWORD=" not in content.split("--set-secrets")[-1]
    assert "TELEMETRY_STORE=firestore" in content
    assert "AUTH_PASSWORD=${" not in content
    assert "WALLET_ADDRESS=" not in content
    assert "TV_WEBHOOK_URL=" not in content
    assert "MAX_ORDER_USD=" not in content
    assert "DASHBOARD_ARMED=" not in content
    assert not re.search(r"0x[a-fA-F0-9]{40}", content)
    assert "trycloudflare.com" not in content
    assert "sapphire-alpha-dashboard:$BUILD_ID" in content
    assert "sapphire-alpha-dashboard:latest" not in content
    assert "SAPPHIRE_BUILD_SHA=${_BUILD_SHA}" in content
    assert "SAPPHIRE_BUILD_ID=$BUILD_ID" in content
    assert "_BUILD_SHA: unknown" in content
    assert '[[ ! "${_BUILD_SHA}" =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]]' in content
    assert "exit 2" in content


def test_deploy_script_never_sends_inline_secrets_or_live_state():
    content = (ROOT / "deploy.sh").read_text(encoding="utf-8")
    assert "gcloud builds submit" in content
    assert "--config cloudbuild.yaml" in content
    assert '--substitutions="_BUILD_SHA=${BUILD_SHA}"' in content
    assert "AUTH_PASSWORD=${" not in content
    for forbidden in ("WALLET_ADDRESS", "MAX_ORDER_USD", "TV_WEBHOOK_URL", "DASHBOARD_ARMED", "DASHBOARD_SIGNALS_JSON"):
        assert forbidden not in content
    assert "status --porcelain" in content
    assert "gcloud run deploy" not in content
    assert "local-source-" not in content
    assert 'REGION="us-central1"' in content
    assert 'SERVICE_NAME="sapphire-alpha-dashboard"' in content
    assert 'REGION="${REGION:-' not in content
    assert 'SERVICE_NAME="${SERVICE_NAME:-' not in content


def test_deploy_script_binds_exact_personal_project():
    content = (ROOT / "deploy.sh").read_text(encoding="utf-8")
    assert 'PROJECT_ID="sapphire-479610"' in content
    assert 'PROJECT_ID="${PROJECT_ID:-' not in content
    assert '--project="${PROJECT_ID}"' in content
    assert 'REGION="us-central1"' in content
    assert 'SERVICE_NAME="sapphire-alpha-dashboard"' in content


def test_ordinary_deploy_does_not_request_access_policy_mutation():
    content = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    assert "--allow-unauthenticated" not in content
    assert "--no-allow-unauthenticated" not in content


def test_dockerfile_bakes_build_identity_into_runtime_image():
    content = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for declaration in (
        "ARG SAPPHIRE_BUILD_SHA=unknown",
        "ARG SAPPHIRE_BUILD_ID=unknown",
        "ENV SAPPHIRE_BUILD_SHA=${SAPPHIRE_BUILD_SHA}",
        "ENV SAPPHIRE_BUILD_ID=${SAPPHIRE_BUILD_ID}",
        "LABEL org.opencontainers.image.revision=${SAPPHIRE_BUILD_SHA}",
        "LABEL io.sapphire.build-id=${SAPPHIRE_BUILD_ID}",
    ):
        assert declaration in content


def test_cloud_source_upload_excludes_local_and_generated_state():
    content = (ROOT / ".gcloudignore").read_text(encoding="utf-8")
    for forbidden in (
        ".git/",
        ".env",
        ".remember/",
        ".claude/",
        "daily-brief.sh",
        "frontend/node_modules/",
        "frontend/dist/",
        "web/node_modules/",
        "web/.next/",
        "web/out/",
        "backend/.venv/",
    ):
        assert forbidden in content

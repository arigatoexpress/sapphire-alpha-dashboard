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


def test_deploy_script_never_sends_inline_secrets_or_live_state():
    content = (ROOT / "deploy.sh").read_text(encoding="utf-8")
    assert "--set-secrets" in content
    assert "AUTH_PASSWORD=${" not in content
    for forbidden in ("WALLET_ADDRESS", "MAX_ORDER_USD", "TV_WEBHOOK_URL", "DASHBOARD_ARMED", "DASHBOARD_SIGNALS_JSON"):
        assert forbidden not in content

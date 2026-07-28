"""Static deployment closure and immutable build-input checks."""

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
DOCKER_BUILDER = (
    "gcr.io/cloud-builders/docker@"
    "sha256:680b2a8d18a794c165cf97a3f9476784d5d962e945d424cb40b3e086cde0c284"
)
CLOUD_SDK = (
    "gcr.io/google.com/cloudsdktool/cloud-sdk@"
    "sha256:96a99902b17be6192e01bd94067d72e9c1c017a042ad970e98eb576070562058"
)


def _cloudbuild() -> dict:
    return json.loads((ROOT / "cloudbuild.yaml").read_text(encoding="utf-8"))


def test_every_production_container_base_is_digest_pinned():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    from_lines = [
        line for line in dockerfile.splitlines() if line.strip().startswith("FROM ")
    ]
    assert len(from_lines) == 4
    assert all(re.search(r"@sha256:[0-9a-f]{64}(?:\s|$)", line) for line in from_lines)
    assert "node:24-bookworm-slim" in dockerfile
    assert "python:3.11.15-slim-trixie" in dockerfile


def test_language_dependency_installations_are_lock_closed():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.count("RUN npm ci") == 2
    assert "npm install" not in dockerfile
    assert "pip install --no-cache-dir --require-hashes -r requirements.lock" in dockerfile
    requirements = (ROOT / "backend/requirements.lock").read_text(encoding="utf-8")
    assert "--hash=sha256:" in requirements
    assert requirements.count("--hash=sha256:") > 47


def test_fonts_are_exact_self_hosted_packages_with_dual_hash_contract():
    layout = (ROOT / "web/src/app/layout.tsx").read_text(encoding="utf-8")
    assert "next/font/google" not in layout
    assert layout.count("@fontsource/") == 12
    assets = json.loads((ROOT / "deploy/assets.sha256.json").read_text())
    assert len(assets["assets"]) == 4
    assert all(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) for item in assets["assets"])
    for lock_name in ("frontend/package-lock.json", "web/package-lock.json"):
        lock = json.loads((ROOT / lock_name).read_text())
        assert lock["lockfileVersion"] == 3
        for package in lock["packages"].values():
            if package.get("resolved", "").startswith("https://registry.npmjs.org/"):
                assert package["integrity"].startswith("sha512-")


def test_cloudbuild_pins_steps_and_runs_cas_immediately_before_deploy():
    config = _cloudbuild()
    assert [step["name"] for step in config["steps"]] == [
        CLOUD_SDK,
        DOCKER_BUILDER,
        DOCKER_BUILDER,
        CLOUD_SDK,
    ]
    final = config["steps"][-1]["args"][-1]
    assert "predeploy-cas" in final
    assert "&& exec gcloud run deploy" in final
    assert "sapphire-alpha-dashboard" in final
    assert "--project sapphire-479610" in final
    assert "--region us-central1" in final
    assert config["options"]["sourceProvenanceHash"] == ["SHA256"]


def test_future_action_uses_existing_exact_source_and_never_implicit_staging():
    content = (ROOT / "deploy.sh").read_text(encoding="utf-8")
    assert "local-preflight" in content
    assert "render-cloudbuild" in content
    assert "gcloud builds submit" in content
    assert "--no-source" in content
    assert "--gcs-source-staging-dir" not in content
    assert "storage cp" not in content
    assert "CreateBucketIfNotExists" not in content
    assert "status --porcelain" in content
    assert 'PROJECT_ID="sapphire-479610"' in content
    assert 'REGION="us-central1"' in content


def test_action_binds_descriptor_preflight_postcheck_wrapper_and_build_config():
    source = (ROOT / "scripts/deploy_contract.py").read_text(encoding="utf-8")
    for artifact in (
        "cloudbuild.yaml",
        "deploy.sh",
        "scripts/deploy_contract.py",
        "scripts/verify_deployment.py",
    ):
        assert f'"{artifact}"' in source
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    assert "_ACTION_DESCRIPTOR_ZLIB_B64" in cloudbuild
    assert "_ACTION_DESCRIPTOR_SHA256" in cloudbuild
    assert "_SOURCE_GENERATION" in cloudbuild
    assert "_SOURCE_OBJECT" in cloudbuild


def test_deploy_manifests_do_not_carry_operational_or_financial_literals():
    content = (
        (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
        + (ROOT / "deploy.sh").read_text(encoding="utf-8")
    )
    for forbidden in (
        "WALLET_ADDRESS=",
        "TV_WEBHOOK_URL=",
        "MAX_ORDER_USD=",
        "DASHBOARD_ARMED=",
        "DASHBOARD_SIGNALS_JSON=",
        "trycloudflare.com",
    ):
        assert forbidden not in content
    assert not re.search(r"0x[a-fA-F0-9]{40}", content)


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

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
    assert len(from_lines) == 6
    external = [line for line in from_lines if not line.startswith("FROM scratch ")]
    assert len(external) == 4
    assert all(re.search(r"@sha256:[0-9a-f]{64}(?:\s|$)", line) for line in external)
    assert from_lines.count("FROM scratch AS frontend-proof") == 1
    assert from_lines.count("FROM scratch AS web-proof") == 1
    assert "node:24-bookworm-slim" in dockerfile
    assert "python:3.11.15-slim-trixie" in dockerfile


def test_language_dependency_installations_are_lock_closed():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.count("RUN npm ci") == 2
    assert "npm install" not in dockerfile
    assert (
        "pip install --no-cache-dir --require-hashes -r requirements.lock" in dockerfile
    )
    requirements = (ROOT / "backend/requirements.lock").read_text(encoding="utf-8")
    assert "--hash=sha256:" in requirements
    assert requirements.count("--hash=sha256:") > 47


def test_fonts_are_exact_self_hosted_packages_with_dual_hash_contract():
    layout = (ROOT / "web/src/app/layout.tsx").read_text(encoding="utf-8")
    assert "next/font/google" not in layout
    assert layout.count("@fontsource/") == 12
    assets = json.loads((ROOT / "deploy/assets.sha256.json").read_text())
    assert len(assets["assets"]) == 4
    assert all(
        re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) for item in assets["assets"]
    )
    for lock_name in ("frontend/package-lock.json", "web/package-lock.json"):
        lock = json.loads((ROOT / lock_name).read_text())
        assert lock["lockfileVersion"] == 3
        for package in lock["packages"].values():
            if package.get("resolved", "").startswith("https://registry.npmjs.org/"):
                assert package["integrity"].startswith("sha512-")


def test_cloudbuild_pins_steps_and_never_deploys_from_a_working_build():
    config = _cloudbuild()
    assert [step["name"] for step in config["steps"]] == [
        CLOUD_SDK,
        DOCKER_BUILDER,
        DOCKER_BUILDER,
    ]
    assert config["steps"][0]["args"][1] == "verify-workspace"
    serialized = json.dumps(config)
    assert "gcloud run deploy" not in serialized
    assert "predeploy-cas" not in serialized
    assert config["options"]["sourceProvenanceHash"] == ["SHA256"]


def test_future_action_is_one_externally_pinned_trusted_launcher():
    wrapper = (ROOT / "deploy.sh").read_text(encoding="utf-8")
    launcher = (ROOT / "scripts/trusted_release.py").read_text(encoding="utf-8")
    assert "SAPPHIRE_TRUSTED_WRAPPER_SHA256" in wrapper
    assert "SAPPHIRE_TRUSTED_LAUNCHER_SHA256" in wrapper
    assert "SAPPHIRE_TRUSTED_PYTHON_SHA256" in wrapper
    assert "SAPPHIRE_TRUSTED_GUARD_SHA256" in wrapper
    assert "SAPPHIRE_TRUSTED_GIT_SHA256" in wrapper
    assert "SAPPHIRE_TRUSTED_GCLOUD_SHA256" in wrapper
    assert "SAPPHIRE_TRUSTED_RENDERED_CONFIG_SHA256" in wrapper
    assert "exec python3" in wrapper
    assert '"gcloud"' in launcher and '"builds"' in launcher and '"submit"' in launcher
    assert "--no-source" in launcher
    assert "deploy_with_provider_cas" in launcher
    assert "gcloud run deploy" not in launcher
    assert "storage cp" not in launcher
    assert "CreateBucketIfNotExists" not in launcher


def test_action_binds_descriptor_preflight_postcheck_wrapper_and_build_config():
    source = (ROOT / "scripts/deploy_contract.py").read_text(encoding="utf-8")
    for artifact in (
        "cloudbuild.yaml",
        "deploy.sh",
        "scripts/deploy_contract.py",
        "scripts/trusted_release.py",
        "scripts/verify_deployment.py",
    ):
        assert f'"{artifact}"' in source
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    assert "_ACTION_DESCRIPTOR_ZLIB_B64" in cloudbuild
    assert "_ACTION_DESCRIPTOR_SHA256" in cloudbuild
    assert "_SOURCE_GENERATION" in cloudbuild
    assert "_SOURCE_OBJECT" in cloudbuild
    assert "_SOURCE_TREE_SHA" in cloudbuild
    assert "_SOURCE_ARCHIVE_MD5" in cloudbuild
    assert "_SOURCE_FILE_COUNT" in cloudbuild


def test_deploy_manifests_do_not_carry_operational_or_financial_literals():
    content = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8") + (
        ROOT / "deploy.sh"
    ).read_text(encoding="utf-8")
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


def test_public_static_build_id_is_the_exact_source_identity():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    config = (ROOT / "web/next.config.ts").read_text(encoding="utf-8")
    # The ARG default is a semantic sentinel — either "unknown" (fail-closed;
    # forces callers to pass --build-arg) or "local-development" (the
    # next.config sentinel that explicitly opts out of a real identity).
    # The trusted-release path passes the exact commit SHA regardless.
    assert (
        "ARG SAPPHIRE_BUILD_SHA=unknown" in dockerfile
        or "ARG SAPPHIRE_BUILD_SHA=local-development" in dockerfile
    )
    assert "ENV SAPPHIRE_BUILD_SHA=${SAPPHIRE_BUILD_SHA}" in dockerfile
    assert "generateBuildId" in config
    assert "process.env.SAPPHIRE_BUILD_SHA" in config
    assert "local-development" in config

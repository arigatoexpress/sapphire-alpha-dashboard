"""Deployment manifests cannot carry operational or financial literals."""

import json
import os
from pathlib import Path
import re
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _cloudbuild_config() -> dict:
    return yaml.safe_load((ROOT / "cloudbuild.yaml").read_text(encoding="utf-8"))


def _deploy_args() -> list[str]:
    matches = [
        step["args"]
        for step in _cloudbuild_config()["steps"]
        if step.get("entrypoint") == "gcloud" and step.get("args", [])[:2] == ["run", "deploy"]
    ]
    assert len(matches) == 1
    return matches[0]


def _option_value(args: list[str], option: str) -> str:
    index = args.index(option)
    return args[index + 1]


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
    deploy_args = _deploy_args()
    forbidden = {
        "--allow-unauthenticated",
        "--no-allow-unauthenticated",
        "set-iam-policy",
        "add-iam-policy-binding",
        "remove-iam-policy-binding",
        "roles/run.invoker",
        "allUsers",
    }
    assert forbidden.isdisjoint(deploy_args)


def test_cloudbuild_deploy_binds_exact_target_semantically():
    deploy_args = _deploy_args()
    assert deploy_args[:3] == ["run", "deploy", "sapphire-alpha-dashboard"]
    assert _option_value(deploy_args, "--project") == "sapphire-479610"
    assert _option_value(deploy_args, "--region") == "us-central1"


def test_cloudbuild_fails_closed_for_wrong_project():
    config = _cloudbuild_config()
    preflight = config["steps"][0]
    assert preflight["entrypoint"] == "bash"
    script = preflight["args"][-1]
    assert '[[ "${PROJECT_ID}" != "sapphire-479610" ]]' in script
    exact_sha = "a" * 40

    wrong_project_script = script.replace("${PROJECT_ID}", "attacker-project").replace(
        "${_BUILD_SHA}", exact_sha
    )
    rejected = subprocess.run(
        ["bash", "-ceu", wrong_project_script],
        check=False,
        text=True,
        capture_output=True,
    )
    assert rejected.returncode == 2
    assert "Refusing Cloud Build project attacker-project" in rejected.stderr

    exact_project_script = script.replace("${PROJECT_ID}", "sapphire-479610").replace(
        "${_BUILD_SHA}", exact_sha
    )
    subprocess.run(["bash", "-ceu", exact_project_script], check=True)


def test_deploy_script_ignores_hostile_target_environment(tmp_path):
    fake_git = tmp_path / "git"
    fake_git.write_text(
        """#!/usr/bin/env python3
import sys

args = sys.argv[1:]
if args[-2:] == ["rev-parse", "HEAD"]:
    print("e479593b27606ad4a8666389c689607c84298094")
elif args[-2:] != ["status", "--porcelain"]:
    raise SystemExit(f"unexpected git invocation: {args!r}")
""",
        encoding="utf-8",
    )
    fake_gcloud = tmp_path / "gcloud"
    fake_gcloud.write_text(
        """#!/usr/bin/env python3
import json
import sys

print("GCLOUD_CALL=" + json.dumps(sys.argv[1:]))
""",
        encoding="utf-8",
    )
    fake_git.chmod(0o700)
    fake_gcloud.chmod(0o700)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path}:{env['PATH']}",
            "PROJECT_ID": "attacker-project",
            "REGION": "attacker-region",
            "SERVICE_NAME": "attacker-service",
            "CLOUDSDK_CORE_PROJECT": "attacker-sdk-project",
            "CLOUDSDK_RUN_REGION": "attacker-sdk-region",
        }
    )
    completed = subprocess.run(
        [str(ROOT / "deploy.sh")],
        cwd=ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    calls = [
        json.loads(line.removeprefix("GCLOUD_CALL="))
        for line in completed.stdout.splitlines()
        if line.startswith("GCLOUD_CALL=")
    ]
    assert calls == [
        [
            "builds",
            "submit",
            ".",
            "--config",
            "cloudbuild.yaml",
            "--project=sapphire-479610",
            "--region=us-central1",
            "--substitutions=_BUILD_SHA=e479593b27606ad4a8666389c689607c84298094",
        ],
        [
            "run",
            "services",
            "describe",
            "sapphire-alpha-dashboard",
            "--project=sapphire-479610",
            "--region=us-central1",
            "--format",
            "value(status.url)",
        ],
    ]


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

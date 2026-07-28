#!/usr/bin/env python3
"""Externally hash-pinned, one-shot production release launcher.

The approval harness is the trust root: it must pin this file and the resolved
Python interpreter before execution. This launcher then verifies the entire
release artifact closure before compiling the release guard from verified bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = Path(__file__).resolve()
GUARD = ROOT / "scripts/deploy_contract.py"
HEX64 = set("0123456789abcdef")
TRUSTED_ARTIFACTS = {
    "Dockerfile",
    "backend/requirements.lock",
    "cloudbuild.yaml",
    "deploy.sh",
    "deploy/assets.sha256.json",
    "frontend/package-lock.json",
    "scripts/deploy_contract.py",
    "scripts/trusted_release.py",
    "scripts/verify_build_inputs.py",
    "scripts/verify_deployment.py",
    "web/package-lock.json",
}


class TrustFailure(ValueError):
    """The external or descriptor trust root did not match."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_digest(name: str) -> str:
    value = os.environ.get(name, "")
    if len(value) != 64 or any(character not in HEX64 for character in value):
        raise TrustFailure("trusted execution contract mismatch")
    return value


def _load_verified_guard(descriptor_path: Path, descriptor_sha256: str) -> Any:
    if _sha256(LAUNCHER) != _required_digest("SAPPHIRE_TRUSTED_LAUNCHER_SHA256"):
        raise TrustFailure("trusted execution contract mismatch")
    if _sha256(ROOT / "deploy.sh") != _required_digest(
        "SAPPHIRE_TRUSTED_WRAPPER_SHA256"
    ):
        raise TrustFailure("trusted execution contract mismatch")
    interpreter = Path(sys.executable).resolve()
    if _sha256(interpreter) != _required_digest("SAPPHIRE_TRUSTED_PYTHON_SHA256"):
        raise TrustFailure("trusted execution contract mismatch")
    for tool, variable in (
        ("git", "SAPPHIRE_TRUSTED_GIT_SHA256"),
        ("gcloud", "SAPPHIRE_TRUSTED_GCLOUD_SHA256"),
    ):
        resolved = shutil.which(tool)
        if resolved is None or _sha256(Path(resolved).resolve()) != _required_digest(
            variable
        ):
            raise TrustFailure("trusted execution contract mismatch")
    raw = descriptor_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != descriptor_sha256:
        raise TrustFailure("trusted execution contract mismatch")
    try:
        descriptor = json.loads(raw)
    except json.JSONDecodeError as error:
        raise TrustFailure("trusted execution contract mismatch") from error
    if (
        not isinstance(descriptor, dict)
        or descriptor.get("schema") != "sapphire/deploy-action/v1"
        or not isinstance(descriptor.get("artifacts"), dict)
        or set(descriptor)
        != {"schema", "target", "source", "precondition", "postcondition", "artifacts"}
        or raw
        != (
            json.dumps(
                descriptor,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        ).encode()
        or set(descriptor["artifacts"]) != TRUSTED_ARTIFACTS
    ):
        raise TrustFailure("trusted execution contract mismatch")
    artifacts = descriptor["artifacts"]
    for relative, expected in artifacts.items():
        if (
            not isinstance(relative, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not isinstance(expected, str)
            or _sha256(ROOT / relative) != expected
        ):
            raise TrustFailure("trusted execution contract mismatch")
    guard_bytes = GUARD.read_bytes()
    guard_sha256 = hashlib.sha256(guard_bytes).hexdigest()
    if (
        guard_sha256 != artifacts.get("scripts/deploy_contract.py")
        or guard_sha256 != _required_digest("SAPPHIRE_TRUSTED_GUARD_SHA256")
        or _sha256(LAUNCHER) != artifacts.get("scripts/trusted_release.py")
        or _sha256(ROOT / "deploy.sh") != artifacts.get("deploy.sh")
    ):
        raise TrustFailure("trusted execution contract mismatch")
    module = types.ModuleType("sapphire_verified_deploy_contract")
    module.__file__ = str(GUARD)
    exec(compile(guard_bytes, str(GUARD), "exec"), module.__dict__)  # noqa: S102
    module._require_descriptor_shape(descriptor)
    return module


def _run(argv: list[str]) -> str:
    completed = subprocess.run(
        argv,
        check=True,
        capture_output=True,
        text=True,
        timeout=3600,
        env={
            **os.environ,
            "CLOUDSDK_CORE_PROJECT": "sapphire-479610",
            "CLOUDSDK_RUN_REGION": "us-central1",
        },
    )
    return completed.stdout


def release(descriptor_path: Path, descriptor_sha256: str) -> dict[str, Any]:
    guard = _load_verified_guard(descriptor_path, descriptor_sha256)
    descriptor, raw = guard.load_descriptor(descriptor_path, descriptor_sha256)
    guard.verify_artifacts(descriptor)
    guard.verify_local_source(descriptor)
    guard.verify_bucket_and_object(descriptor)
    guard.verify_predeploy_cas(descriptor)
    with tempfile.TemporaryDirectory(prefix="sapphire-release-") as directory:
        rendered = Path(directory) / "cloudbuild.json"
        guard.render_cloudbuild(
            ROOT / "cloudbuild.yaml",
            descriptor,
            raw,
            descriptor_sha256,
            rendered,
        )
        if _sha256(rendered) != _required_digest(
            "SAPPHIRE_TRUSTED_RENDERED_CONFIG_SHA256"
        ):
            raise TrustFailure("trusted execution contract mismatch")
        build_id = _run(
            [
                "gcloud",
                "builds",
                "submit",
                "--no-source",
                f"--config={rendered}",
                "--project=sapphire-479610",
                "--region=us-central1",
                "--format=value(id)",
                "--quiet",
            ]
        ).strip()
    guard.verify_build_record(
        descriptor,
        descriptor_sha256,
        build_id,
        require_success=True,
    )
    build = guard._json_command(
        guard._run,
        guard._gcloud("builds", "describe", build_id, "--format=json"),
    )
    image = guard.immutable_image(build, build_id)
    guard.verify_registry_digest(build_id, image)
    guard.deploy_with_provider_cas(descriptor, image)
    deadline = time.monotonic() + 600
    while True:
        try:
            postdeploy = guard.verify_postdeploy(
                descriptor, descriptor_sha256, build_id
            )
            break
        except guard.ContractViolation:
            if time.monotonic() >= deadline:
                raise
            time.sleep(5)
    return {
        "schema": "sapphire/trusted-release/v1",
        "ok": True,
        "build_id_sha256": hashlib.sha256(build_id.encode()).hexdigest(),
        "immutable_image_sha256": hashlib.sha256(image.encode()).hexdigest(),
        "postcondition_sha256": postdeploy["postcondition_sha256"],
    }


def _load_preparation_guard() -> Any:
    guard = types.ModuleType("sapphire_release_preparation")
    guard.__file__ = str(GUARD)
    guard_bytes = GUARD.read_bytes()
    exec(compile(guard_bytes, str(GUARD), "exec"), guard.__dict__)  # noqa: S102
    return guard


def seal(output: Path) -> dict[str, Any]:
    # Source sealing is read-only with respect to the repository. The generated
    # archive is local staging material and is mode 0600.
    guard = _load_preparation_guard()
    if _run(["git", "-C", str(ROOT), "status", "--porcelain"]):
        raise TrustFailure("source sealing requires a clean Git tree")
    source = guard.seal_source(ROOT)
    source["commit_sha"] = _run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).strip()
    source["tree_sha"] = _run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD^{tree}"]
    ).strip()
    output.write_bytes(source.pop("archive"))
    output.chmod(0o600)
    return {"schema": "sapphire/source-seal/v1", "ok": True, **source}


def draft_action(object_name: str, generation: int, output: Path) -> dict[str, Any]:
    guard = _load_preparation_guard()
    if _run(["git", "-C", str(ROOT), "status", "--porcelain"]):
        raise TrustFailure("action drafting requires a clean Git tree")
    source_sha = _run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).strip()
    with tempfile.TemporaryDirectory(prefix="sapphire-surface-proof-") as directory:
        surface_root = Path(directory)
        for target in ("frontend-proof", "web-proof"):
            destination = surface_root / target
            _run(
                [
                    "docker",
                    "buildx",
                    "build",
                    "--platform=linux/amd64",
                    f"--build-arg=SAPPHIRE_BUILD_SHA={source_sha}",
                    f"--target={target}",
                    f"--output=type=local,dest={destination}",
                    str(ROOT),
                ]
            )
        if _run(["git", "-C", str(ROOT), "status", "--porcelain"]):
            raise TrustFailure("surface build changed the reviewed Git tree")
        descriptor = guard.draft_descriptor(
            object_name,
            generation,
            ROOT,
            operator_surface=surface_root / "frontend-proof/surface",
            public_surface=surface_root / "web-proof/surface",
        )
    raw = guard.canonical(descriptor)
    output.write_bytes(raw)
    output.chmod(0o600)
    return {
        "schema": "sapphire/action-draft/v1",
        "ok": True,
        "descriptor_sha256": hashlib.sha256(raw).hexdigest(),
        "substitution_bytes": len(guard.encode_descriptor(raw)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--descriptor", type=Path, required=True)
    run_parser.add_argument("--descriptor-sha256", required=True)
    seal_parser = commands.add_parser("seal-source")
    seal_parser.add_argument("--output", type=Path, required=True)
    draft_parser = commands.add_parser("draft-action")
    draft_parser.add_argument("--object", required=True)
    draft_parser.add_argument("--generation", type=int, required=True)
    draft_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "run":
            result = release(args.descriptor, args.descriptor_sha256)
        elif args.command == "seal-source":
            result = seal(args.output)
        else:
            result = draft_action(args.object, args.generation, args.output)
    except Exception:
        result = {
            "schema": "sapphire/trusted-release-error/v1",
            "ok": False,
            "error": "release contract mismatch",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

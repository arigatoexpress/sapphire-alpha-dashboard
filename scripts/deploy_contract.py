#!/usr/bin/env python3
"""Content-addressed release guard for the Sapphire production service.

The module is intentionally stdlib-only so the exact reviewed copy can run in
the pinned Cloud SDK builder. It never prints runtime environment values.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import zlib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "sapphire-479610"
REGION = "us-central1"
SERVICE = "sapphire-alpha-dashboard"
SERVICE_ACCOUNT = "sapphire-dashboard-sa@sapphire-479610.iam.gserviceaccount.com"
IMAGE_REPOSITORY = "gcr.io/sapphire-479610/sapphire-alpha-dashboard"
STAGING_BUCKET = "sapphire-479610_cloudbuild"
SCHEMA = "sapphire/deploy-action/v1"
REQUIRED_ARTIFACTS = {
    "Dockerfile",
    "cloudbuild.yaml",
    "deploy.sh",
    "deploy/assets.sha256.json",
    "backend/requirements.lock",
    "frontend/package-lock.json",
    "web/package-lock.json",
    "scripts/deploy_contract.py",
    "scripts/verify_build_inputs.py",
    "scripts/verify_deployment.py",
}
HEX40_OR_64 = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
HEX64 = re.compile(r"[0-9a-f]{64}")
Run = Callable[[Sequence[str]], str]
Fetch = Callable[[str], tuple[int, str]]


class ContractViolation(ValueError):
    """A closed release precondition did not match."""


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(argv: Sequence[str]) -> str:
    completed = subprocess.run(
        list(argv),
        check=True,
        capture_output=True,
        text=True,
        timeout=1800,
        env={
            **os.environ,
            "CLOUDSDK_CORE_PROJECT": PROJECT,
            "CLOUDSDK_RUN_REGION": REGION,
        },
    )
    return completed.stdout


def fetch_http(url: str) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": "sapphire-release-guard/1"})
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed descriptor origin
            return response.status, response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


def _json_command(run: Run, argv: Sequence[str]) -> dict[str, Any]:
    value = json.loads(run(argv))
    if not isinstance(value, dict):
        raise ContractViolation("remote projection mismatch")
    return value


def _gcloud(*args: str, region: bool = True) -> list[str]:
    command = ["gcloud", *args, f"--project={PROJECT}"]
    if region:
        command.append(f"--region={REGION}")
    return command


def _nested(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _iam_sha256(policy: Mapping[str, Any]) -> str:
    return sha256_bytes(
        canonical(
            {
                "bindings": policy.get("bindings", []),
                "version": policy.get("version", 1),
            }
        )
    )


def normalize_environment(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise ContractViolation("runtime environment mismatch")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise ContractViolation("runtime environment mismatch")
        name = item.get("name")
        if not isinstance(name, str) or not name or name in seen:
            raise ContractViolation("runtime environment mismatch")
        seen.add(name)
        if "value" in item and "valueFrom" not in item:
            value = item["value"]
            if not isinstance(value, str):
                raise ContractViolation("runtime environment mismatch")
            record = {"name": name, "plain_value": value}
        elif "valueFrom" in item and "value" not in item:
            value_from = item["valueFrom"]
            if not isinstance(value_from, Mapping):
                raise ContractViolation("runtime environment mismatch")
            record = {"name": name, "value_source": value_from}
        else:
            raise ContractViolation("runtime environment mismatch")
        normalized.append(record)
    return sorted(normalized, key=lambda item: item["name"])


def environment_commitments(items: Any) -> dict[str, Any]:
    normalized = normalize_environment(items)
    names = [item["name"] for item in normalized]
    return {
        "key_count": len(names),
        "names_sha256": sha256_bytes(canonical(names)),
        "full_sha256": sha256_bytes(canonical(normalized)),
    }


def bucket_projection(bucket: Mapping[str, Any]) -> dict[str, Any]:
    """Return configuration only; timestamps and ACL member values stay hashed."""
    return {
        "name": bucket.get("name"),
        "location": bucket.get("location"),
        "location_type": bucket.get("location_type"),
        "default_storage_class": bucket.get("default_storage_class"),
        "public_access_prevention": bucket.get("public_access_prevention"),
        "uniform_bucket_level_access": bucket.get("uniform_bucket_level_access"),
        "rpo": bucket.get("rpo"),
        "generation": bucket.get("generation"),
        "metageneration": bucket.get("metageneration"),
        "lifecycle_config": bucket.get("lifecycle_config"),
        "soft_delete_policy": bucket.get("soft_delete_policy"),
        "acl_sha256": sha256_bytes(canonical(bucket.get("acl", []))),
        "default_acl_sha256": sha256_bytes(canonical(bucket.get("default_acl", []))),
    }


def _container(service: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    template_spec = _nested(service, "spec", "template", "spec")
    containers = (
        template_spec.get("containers") if isinstance(template_spec, Mapping) else None
    )
    if (
        not isinstance(template_spec, Mapping)
        or not isinstance(containers, list)
        or len(containers) != 1
        or not isinstance(containers[0], Mapping)
    ):
        raise ContractViolation("service projection mismatch")
    return template_spec, containers[0]


def live_snapshot(run: Run = _run, fetch: Fetch = fetch_http) -> dict[str, Any]:
    service = _json_command(
        run, _gcloud("run", "services", "describe", SERVICE, "--format=json")
    )
    metadata = service.get("metadata")
    status = service.get("status")
    if not isinstance(metadata, Mapping) or not isinstance(status, Mapping):
        raise ContractViolation("service projection mismatch")
    template_spec, container = _container(service)
    ready = status.get("latestReadyRevisionName")
    created = status.get("latestCreatedRevisionName")
    if not isinstance(ready, str) or not isinstance(created, str):
        raise ContractViolation("revision projection mismatch")
    ready_record = _json_command(
        run,
        _gcloud("run", "revisions", "describe", ready, "--format=json"),
    )
    created_record = (
        ready_record
        if created == ready
        else _json_command(
            run,
            _gcloud("run", "revisions", "describe", created, "--format=json"),
        )
    )
    policy = _json_command(
        run,
        _gcloud(
            "run",
            "services",
            "get-iam-policy",
            SERVICE,
            "--format=json",
        ),
    )
    service_url = status.get("url")
    if not isinstance(service_url, str) or not service_url.startswith("https://"):
        raise ContractViolation("service URL mismatch")
    build_status, _ = fetch(f"{service_url}/api/build")
    return {
        "generation": metadata.get("generation"),
        "observed_generation": status.get("observedGeneration"),
        "ready_revision": ready,
        "ready_image_digest": _nested(ready_record, "status", "imageDigest"),
        "created_revision": created,
        "created_image_digest": _nested(created_record, "status", "imageDigest"),
        "traffic": status.get("traffic"),
        "iam_sha256": _iam_sha256(policy),
        "service_account": template_spec.get("serviceAccountName"),
        "environment": environment_commitments(container.get("env")),
        "service_url": service_url,
        "build_endpoint_status": build_status,
    }


def artifact_hashes(root: Path = ROOT) -> dict[str, str]:
    return {name: sha256_file(root / name) for name in sorted(REQUIRED_ARTIFACTS)}


def _require_descriptor_shape(descriptor: Mapping[str, Any]) -> None:
    if descriptor.get("schema") != SCHEMA:
        raise ContractViolation("descriptor mismatch")
    target = descriptor.get("target")
    source = descriptor.get("source")
    precondition = descriptor.get("precondition")
    postcondition = descriptor.get("postcondition")
    artifacts = descriptor.get("artifacts")
    if not all(
        isinstance(value, Mapping)
        for value in (target, source, precondition, postcondition, artifacts)
    ):
        raise ContractViolation("descriptor mismatch")
    if target != {
        "project": PROJECT,
        "region": REGION,
        "service": SERVICE,
        "service_account": SERVICE_ACCOUNT,
        "image_repository": IMAGE_REPOSITORY,
    }:
        raise ContractViolation("target mismatch")
    if set(artifacts) != REQUIRED_ARTIFACTS:
        raise ContractViolation("artifact closure mismatch")
    if any(HEX64.fullmatch(value) is None for value in artifacts.values()):
        raise ContractViolation("artifact closure mismatch")
    if HEX40_OR_64.fullmatch(str(source.get("commit_sha", ""))) is None:
        raise ContractViolation("source identity mismatch")
    for key in ("archive_sha256", "manifest_sha256"):
        if HEX64.fullmatch(str(source.get(key, ""))) is None:
            raise ContractViolation("source identity mismatch")
    if source.get("bucket") != STAGING_BUCKET:
        raise ContractViolation("staging target mismatch")
    if not isinstance(source.get("generation"), int) or source["generation"] <= 0:
        raise ContractViolation("source generation mismatch")
    object_name = source.get("object")
    if (
        not isinstance(object_name, str)
        or not object_name.startswith("source/sapphire/")
        or not object_name.endswith(".tar.gz")
        or ".." in object_name
    ):
        raise ContractViolation("source object mismatch")
    if HEX64.fullmatch(str(source.get("bucket_configuration_sha256", ""))) is None:
        raise ContractViolation("bucket contract mismatch")


def decode_descriptor(encoded: str, expected_sha256: str) -> dict[str, Any]:
    if HEX64.fullmatch(expected_sha256) is None:
        raise ContractViolation("descriptor digest mismatch")
    try:
        raw = zlib.decompress(base64.b64decode(encoded, validate=True))
        descriptor = json.loads(raw)
    except Exception as error:
        raise ContractViolation("descriptor mismatch") from error
    if sha256_bytes(raw) != expected_sha256 or not isinstance(descriptor, dict):
        raise ContractViolation("descriptor digest mismatch")
    if raw != canonical(descriptor):
        raise ContractViolation("descriptor encoding mismatch")
    _require_descriptor_shape(descriptor)
    return descriptor


def load_descriptor(path: Path, expected_sha256: str) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    if sha256_bytes(raw) != expected_sha256:
        raise ContractViolation("descriptor digest mismatch")
    descriptor = json.loads(raw)
    if not isinstance(descriptor, dict):
        raise ContractViolation("descriptor mismatch")
    if raw != canonical(descriptor):
        raise ContractViolation("descriptor encoding mismatch")
    _require_descriptor_shape(descriptor)
    return descriptor, raw


def verify_artifacts(descriptor: Mapping[str, Any], root: Path = ROOT) -> None:
    if artifact_hashes(root) != descriptor.get("artifacts"):
        raise ContractViolation("artifact closure mismatch")


def verify_bucket_and_object(
    descriptor: Mapping[str, Any], run: Run = _run
) -> dict[str, str]:
    source = descriptor["source"]
    bucket = _json_command(
        run,
        _gcloud(
            "storage",
            "buckets",
            "describe",
            f"gs://{STAGING_BUCKET}",
            "--format=json",
            region=False,
        ),
    )
    if sha256_bytes(canonical(bucket_projection(bucket))) != source[
        "bucket_configuration_sha256"
    ]:
        raise ContractViolation("bucket contract mismatch")
    uri = f"gs://{STAGING_BUCKET}/{source['object']}#{source['generation']}"
    obj = _json_command(
        run,
        _gcloud("storage", "objects", "describe", uri, "--format=json", region=False),
    )
    metadata = obj.get("metadata")
    if (
        obj.get("bucket") not in (None, STAGING_BUCKET)
        or obj.get("name") != source["object"]
        or int(obj.get("generation", 0)) != source["generation"]
        or not isinstance(metadata, Mapping)
        or metadata.get("sha256") != source["archive_sha256"]
    ):
        raise ContractViolation("source object contract mismatch")
    return {"bucket": STAGING_BUCKET, "object_generation": str(source["generation"])}


def verify_predeploy_cas(
    descriptor: Mapping[str, Any],
    run: Run = _run,
    fetch: Fetch = fetch_http,
) -> dict[str, Any]:
    if live_snapshot(run, fetch) != descriptor.get("precondition"):
        raise ContractViolation("remote state mismatch")
    return {
        "schema": "sapphire/predeploy-cas/v1",
        "ok": True,
        "precondition_sha256": sha256_bytes(canonical(descriptor["precondition"])),
    }


def source_provenance_exact(
    build: Mapping[str, Any], descriptor: Mapping[str, Any]
) -> bool:
    source = descriptor["source"]
    expected_storage = {
        "bucket": source["bucket"],
        "object": source["object"],
        "generation": str(source["generation"]),
    }
    submitted = _nested(build, "source", "storageSource")
    resolved = _nested(build, "sourceProvenance", "resolvedStorageSource")
    if not isinstance(submitted, Mapping) or not isinstance(resolved, Mapping):
        return False
    submitted_projection = {
        "bucket": submitted.get("bucket"),
        "object": submitted.get("object"),
        "generation": str(submitted.get("generation", "")),
    }
    resolved_projection = {
        "bucket": resolved.get("bucket"),
        "object": resolved.get("object"),
        "generation": str(resolved.get("generation", "")),
    }
    file_hashes = _nested(build, "sourceProvenance", "fileHashes")
    exact_key = f"gs://{source['bucket']}/{source['object']}"
    expected_hash = base64.b64encode(
        bytes.fromhex(source["archive_sha256"])
    ).decode("ascii")
    return (
        submitted_projection == expected_storage
        and resolved_projection == expected_storage
        and isinstance(file_hashes, Mapping)
        and set(file_hashes) == {exact_key}
        and file_hashes[exact_key]
        == {"fileHash": [{"type": "SHA256", "value": expected_hash}]}
    )


def verify_build_record(
    descriptor: Mapping[str, Any],
    descriptor_sha256: str,
    build_id: str,
    run: Run = _run,
    *,
    require_success: bool = False,
) -> dict[str, Any]:
    if not build_id:
        raise ContractViolation("build identity mismatch")
    build = _json_command(
        run,
        _gcloud("builds", "describe", build_id, "--format=json"),
    )
    if build.get("id") != build_id or (
        require_success and build.get("status") != "SUCCESS"
    ):
        raise ContractViolation("build identity mismatch")
    if not source_provenance_exact(build, descriptor):
        raise ContractViolation("source provenance mismatch")
    substitutions = build.get("substitutions")
    if not isinstance(substitutions, Mapping):
        raise ContractViolation("build substitutions mismatch")
    source = descriptor["source"]
    expected_custom = {
        "_ACTION_DESCRIPTOR_SHA256": descriptor_sha256,
        "_BUILD_SHA": source["commit_sha"],
        "_SOURCE_ARCHIVE_SHA256": source["archive_sha256"],
        "_SOURCE_GENERATION": str(source["generation"]),
        "_SOURCE_MANIFEST_SHA256": source["manifest_sha256"],
        "_SOURCE_OBJECT": source["object"],
    }
    actual_custom = {
        key: str(value) for key, value in substitutions.items() if key.startswith("_")
    }
    encoded_descriptor = actual_custom.pop("_ACTION_DESCRIPTOR_ZLIB_B64", "")
    try:
        submitted_descriptor = decode_descriptor(
            encoded_descriptor, descriptor_sha256
        )
    except ContractViolation:
        raise ContractViolation("build substitutions mismatch") from None
    if submitted_descriptor != descriptor or actual_custom != expected_custom:
        raise ContractViolation("build substitutions mismatch")
    return {
        "schema": "sapphire/build-provenance/v1",
        "ok": True,
        "build_id_sha256": sha256_bytes(build_id.encode()),
        "source_identity_sha256": sha256_bytes(canonical(expected_custom)),
    }


def verify_postdeploy(
    descriptor: Mapping[str, Any],
    descriptor_sha256: str,
    build_id: str,
    run: Run = _run,
    fetch: Fetch = fetch_http,
) -> dict[str, Any]:
    verify_build_record(
        descriptor,
        descriptor_sha256,
        build_id,
        run,
        require_success=True,
    )
    build = _json_command(
        run,
        _gcloud("builds", "describe", build_id, "--format=json"),
    )
    current = live_snapshot(run, fetch)
    previous = descriptor["precondition"]
    expected = descriptor["postcondition"]
    ready = current["ready_revision"]
    images = _nested(build, "results", "images")
    image = images[0] if isinstance(images, list) and len(images) == 1 else None
    digest = image.get("digest") if isinstance(image, Mapping) else None
    name = image.get("name") if isinstance(image, Mapping) else None
    checks = {
        "generation_plus_one": current["generation"] == previous["generation"] + 1,
        "generation_observed": current["observed_generation"]
        == current["generation"],
        "new_ready_revision": ready
        not in {previous["ready_revision"], previous["created_revision"]},
        "ready_equals_created": ready == current["created_revision"],
        "traffic_exact": current["traffic"]
        == [{"percent": 100, "revisionName": ready}],
        "iam_exact": current["iam_sha256"] == expected.get("iam_sha256"),
        "service_account_exact": current["service_account"]
        == expected.get("service_account"),
        "environment_exact": current["environment"] == expected.get("environment"),
        "service_url_exact": current["service_url"] == expected.get("service_url"),
        "build_endpoint_exact": current["build_endpoint_status"] == 200,
        "output_image_exact": (
            isinstance(digest, str)
            and HEX64.fullmatch(digest.removeprefix("sha256:")) is not None
            and name == f"{IMAGE_REPOSITORY}:{build_id}"
            and current["ready_image_digest"] == f"{IMAGE_REPOSITORY}@{digest}"
        ),
    }
    if not all(checks.values()):
        raise ContractViolation("postdeploy state mismatch")
    return {
        "schema": "sapphire/postdeploy-cas/v1",
        "ok": True,
        "checks": checks,
        "postcondition_sha256": sha256_bytes(canonical(expected)),
    }


def render_cloudbuild(
    template_path: Path,
    descriptor: Mapping[str, Any],
    raw_descriptor: bytes,
    descriptor_sha256: str,
    output: Path,
) -> None:
    config = json.loads(template_path.read_text(encoding="utf-8"))
    source = descriptor["source"]
    config["source"] = {
        "storageSource": {
            "bucket": source["bucket"],
            "object": source["object"],
            "generation": source["generation"],
        }
    }
    config["substitutions"] = {
        "_ACTION_DESCRIPTOR_ZLIB_B64": base64.b64encode(
            zlib.compress(raw_descriptor, level=9)
        ).decode("ascii"),
        "_ACTION_DESCRIPTOR_SHA256": descriptor_sha256,
        "_BUILD_SHA": source["commit_sha"],
        "_SOURCE_ARCHIVE_SHA256": source["archive_sha256"],
        "_SOURCE_GENERATION": str(source["generation"]),
        "_SOURCE_MANIFEST_SHA256": source["manifest_sha256"],
        "_SOURCE_OBJECT": source["object"],
    }
    output.write_text(json.dumps(config, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(output, 0o600)


def _safe_main(action: Callable[[], dict[str, Any] | None]) -> int:
    try:
        result = action() or {"ok": True}
    except Exception:
        result = {
            "schema": "sapphire/release-guard-error/v1",
            "ok": False,
            "error": "contract violation",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    local = commands.add_parser("local-preflight")
    local.add_argument("--descriptor", type=Path, required=True)
    local.add_argument("--descriptor-sha256", required=True)

    render = commands.add_parser("render-cloudbuild")
    render.add_argument("--descriptor", type=Path, required=True)
    render.add_argument("--descriptor-sha256", required=True)
    render.add_argument("--template", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)

    build = commands.add_parser("verify-build")
    build.add_argument("--descriptor-zlib-b64", required=True)
    build.add_argument("--descriptor-sha256", required=True)
    build.add_argument("--build-id", required=True)
    build.add_argument("--require-success", action="store_true")

    cas = commands.add_parser("predeploy-cas")
    cas.add_argument("--descriptor-zlib-b64", required=True)
    cas.add_argument("--descriptor-sha256", required=True)
    cas.add_argument("--build-id", required=True)

    post = commands.add_parser("postdeploy")
    post.add_argument("--descriptor-zlib-b64", required=True)
    post.add_argument("--descriptor-sha256", required=True)
    post.add_argument("--build-id", required=True)
    args = parser.parse_args()

    if args.command == "local-preflight":
        def execute_local() -> dict[str, Any]:
            descriptor, _ = load_descriptor(
                args.descriptor, args.descriptor_sha256
            )
            verify_artifacts(descriptor)
            verify_bucket_and_object(descriptor)
            return verify_predeploy_cas(descriptor)

        return _safe_main(execute_local)

    if args.command == "render-cloudbuild":
        def execute_render() -> dict[str, Any]:
            descriptor, raw = load_descriptor(
                args.descriptor, args.descriptor_sha256
            )
            verify_artifacts(descriptor)
            render_cloudbuild(
                args.template,
                descriptor,
                raw,
                args.descriptor_sha256,
                args.output,
            )
            return {
                "schema": "sapphire/cloudbuild-render/v1",
                "ok": True,
                "rendered_sha256": sha256_file(args.output),
            }

        return _safe_main(execute_render)

    descriptor = decode_descriptor(
        args.descriptor_zlib_b64, args.descriptor_sha256
    )
    if args.command == "verify-build":
        return _safe_main(
            lambda: (
                verify_artifacts(descriptor),
                verify_build_record(
                    descriptor,
                    args.descriptor_sha256,
                    args.build_id,
                    require_success=args.require_success,
                ),
            )[1]
        )
    if args.command == "postdeploy":
        return _safe_main(
            lambda: (
                verify_artifacts(descriptor),
                verify_postdeploy(
                    descriptor,
                    args.descriptor_sha256,
                    args.build_id,
                ),
            )[1]
        )
    return _safe_main(
        lambda: (
            verify_artifacts(descriptor),
            verify_build_record(
                descriptor, args.descriptor_sha256, args.build_id
            ),
            verify_predeploy_cas(descriptor),
        )[2]
    )


if __name__ == "__main__":
    raise SystemExit(main())

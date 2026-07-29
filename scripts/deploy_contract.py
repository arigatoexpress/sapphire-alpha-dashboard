#!/usr/bin/env python3
"""Content-addressed release guard for the Sapphire production service.

The module is intentionally stdlib-only so the exact reviewed copy can run in
the pinned Cloud SDK builder. It never prints runtime environment values.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
import zlib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "sapphire-479610"
PROJECT_NUMBER = "267358751314"
REGION = "us-central1"
SERVICE = "sapphire-alpha-dashboard"
SERVICE_ACCOUNT = "sapphire-dashboard-sa@sapphire-479610.iam.gserviceaccount.com"
IMAGE_REPOSITORY = "gcr.io/sapphire-479610/sapphire-alpha-dashboard"
STAGING_BUCKET = "sapphire-479610_cloudbuild"
SCHEMA = "sapphire/deploy-action/v1"
SOURCE_MANIFEST_NAME = ".sapphire-source-manifest.json"
MAX_SUBSTITUTION_BYTES = 4000
PUBLIC_ENVIRONMENT = {
    "AUTH_USERNAME": "sapphire",
    "PUBLIC_READ_ONLY": "1",
    "PUBLIC_TELEMETRY_DELAY_SECONDS": "0",
    "TELEMETRY_STORE": "firestore",
    "TELEMETRY_FIRESTORE_COLLECTION": "sapphire_live_v1",
}
REQUIRED_ARTIFACTS = {
    "Dockerfile",
    "cloudbuild.yaml",
    "deploy.sh",
    "deploy/assets.sha256.json",
    "backend/requirements.lock",
    "frontend/package-lock.json",
    "web/package-lock.json",
    "scripts/deploy_contract.py",
    "scripts/trusted_release.py",
    "scripts/verify_build_inputs.py",
    "scripts/verify_deployment.py",
}
HEX40_OR_64 = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX32 = re.compile(r"[0-9a-f]{32}")
Run = Callable[[Sequence[str]], str]
Fetch = Callable[[str], tuple[int, str]]
ReadBytes = Callable[[Sequence[str]], bytes]


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


def _decode_digest(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)


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


def _run_bytes(argv: Sequence[str]) -> bytes:
    completed = subprocess.run(
        list(argv),
        check=True,
        capture_output=True,
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
        if set(item) == {"name", "value"}:
            value = item["value"]
            if not isinstance(value, str):
                raise ContractViolation("runtime environment mismatch")
            record = {"name": name, "plain_value": value}
        elif set(item) == {"name", "valueFrom"}:
            value_from = item["valueFrom"]
            if not isinstance(value_from, Mapping):
                raise ContractViolation("runtime environment mismatch")
            record = {"name": name, "value_source": value_from}
        elif set(item) == {"name"}:
            record = {"name": name, "plain_value": ""}
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


def projected_environment(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise ContractViolation("runtime environment mismatch")
    projected: dict[str, dict[str, Any]] = {}
    for item in items:
        if (
            not isinstance(item, Mapping)
            or not isinstance(item.get("name"), str)
            or item["name"] in projected
        ):
            raise ContractViolation("runtime environment mismatch")
        projected[item["name"]] = copy.deepcopy(dict(item))
    for name, value in PUBLIC_ENVIRONMENT.items():
        projected[name] = {"name": name, "value": value}
    return [projected[name] for name in sorted(projected)]


def surface_manifest(root: Path, entrypoint_url: str) -> dict[str, Any]:
    if not root.is_dir():
        raise ContractViolation("frontend surface mismatch")
    entries: list[str] = []
    base = root.resolve(strict=True)
    for candidate in sorted(base.rglob("*")):
        if candidate.is_symlink():
            continue
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(base):
            raise ContractViolation("frontend surface mismatch")
        if not resolved.is_file():
            continue
        relative = resolved.relative_to(base).as_posix()
        size = resolved.stat().st_size
        entries.append(f"{relative}\0{size}\0{sha256_file(resolved)}\n")
    entrypoint = base / "index.html"
    if not entries or not entrypoint.is_file():
        raise ContractViolation("frontend surface mismatch")
    return {
        "entrypoint_url": entrypoint_url,
        "entrypoint_sha256": sha256_file(entrypoint),
        "asset_count": len(entries),
        "manifest_sha256": sha256_bytes("".join(entries).encode()),
    }


def tracked_files(root: Path = ROOT) -> list[dict[str, str]]:
    """Return the exact stage-0 Git index closure used by the source seal."""
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-s", "-z"],
        check=True,
        capture_output=True,
        timeout=30,
    )
    records: list[dict[str, str]] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        metadata, separator, path_bytes = raw.partition(b"\t")
        parts = metadata.decode("ascii").split()
        if (
            not separator
            or len(parts) != 3
            or parts[2] != "0"
            or parts[0] not in {"100644", "100755"}
        ):
            raise ContractViolation("Git source closure mismatch")
        path = path_bytes.decode("utf-8")
        if not path or path.startswith("/") or ".." in Path(path).parts or "\n" in path:
            raise ContractViolation("Git source closure mismatch")
        records.append({"path": path, "mode": parts[0], "oid": parts[1]})
    if not records or records != sorted(records, key=lambda item: item["path"]):
        raise ContractViolation("Git source closure mismatch")
    return records


def source_manifest(root: Path = ROOT) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for record in tracked_files(root):
        path = root / record["path"]
        if path.is_symlink() or not path.is_file():
            raise ContractViolation("Git source closure mismatch")
        data = path.read_bytes()
        object_hash = record.get("oid")
        if object_hash is None:
            object_hash = hashlib.sha1(
                f"blob {len(data)}\0".encode() + data,
                usedforsecurity=False,
            ).hexdigest()
        if HEX40_OR_64.fullmatch(object_hash) is None:
            raise ContractViolation("Git source closure mismatch")
        manifest.append(
            {
                "path": record["path"],
                "mode": record["mode"],
                "git_blob_oid": object_hash,
                "sha256": sha256_bytes(data),
                "size": len(data),
            }
        )
    return manifest


def seal_source(root: Path = ROOT) -> dict[str, Any]:
    """Create byte-reproducible gzip/tar bytes from the tracked source closure."""
    manifest = source_manifest(root)
    manifest_bytes = canonical(manifest)
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        manifest_info = tarfile.TarInfo(SOURCE_MANIFEST_NAME)
        manifest_info.size = len(manifest_bytes)
        manifest_info.mode = 0o644
        manifest_info.mtime = 0
        manifest_info.uid = 0
        manifest_info.gid = 0
        manifest_info.uname = ""
        manifest_info.gname = ""
        tar.addfile(manifest_info, io.BytesIO(manifest_bytes))
        for record in manifest:
            data = (root / record["path"]).read_bytes()
            info = tarfile.TarInfo(record["path"])
            info.size = len(data)
            info.mode = 0o755 if record["mode"] == "100755" else 0o644
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    gzip_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=gzip_buffer, mode="wb", filename="", mtime=0) as zipped:
        zipped.write(tar_buffer.getvalue())
    archive = gzip_buffer.getvalue()
    return {
        "archive": archive,
        "archive_sha256": sha256_bytes(archive),
        "archive_md5": hashlib.md5(archive, usedforsecurity=False).hexdigest(),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "file_count": len(manifest),
    }


def verify_workspace(
    descriptor: Mapping[str, Any], root: Path = ROOT
) -> dict[str, Any]:
    source = descriptor["source"]
    manifest_path = root / SOURCE_MANIFEST_NAME
    raw = manifest_path.read_bytes()
    if sha256_bytes(raw) != source["manifest_sha256"]:
        raise ContractViolation("source manifest mismatch")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ContractViolation("source manifest mismatch") from error
    if (
        not isinstance(manifest, list)
        or len(manifest) != source["file_count"]
        or raw != canonical(manifest)
    ):
        raise ContractViolation("source manifest mismatch")
    expected_paths = {SOURCE_MANIFEST_NAME}
    last_path = ""
    for item in manifest:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"path", "mode", "git_blob_oid", "sha256", "size"}
            or item["mode"] not in {"100644", "100755"}
            or not isinstance(item["path"], str)
            or Path(item["path"]).is_absolute()
            or ".." in Path(item["path"]).parts
            or HEX64.fullmatch(str(item["sha256"])) is None
            or HEX40_OR_64.fullmatch(str(item["git_blob_oid"])) is None
            or not isinstance(item["size"], int)
            or item["size"] < 0
        ):
            raise ContractViolation("source manifest mismatch")
        if item["path"] <= last_path:
            raise ContractViolation("source manifest mismatch")
        last_path = item["path"]
        path = root / item["path"]
        if item["path"] in expected_paths or path.is_symlink() or not path.is_file():
            raise ContractViolation("source manifest mismatch")
        data = path.read_bytes()
        actual_mode = "100755" if path.stat().st_mode & 0o111 else "100644"
        hash_function = (
            hashlib.sha1 if len(item["git_blob_oid"]) == 40 else hashlib.sha256
        )
        actual_blob_oid = hash_function(
            f"blob {len(data)}\0".encode() + data,
            usedforsecurity=False,
        ).hexdigest()
        if (
            len(data) != item["size"]
            or sha256_bytes(data) != item["sha256"]
            or actual_blob_oid != item["git_blob_oid"]
            or actual_mode != item["mode"]
        ):
            raise ContractViolation("source manifest mismatch")
        expected_paths.add(item["path"])
    observed_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if observed_paths != expected_paths:
        raise ContractViolation("source manifest mismatch")
    return {
        "schema": "sapphire/source-workspace/v1",
        "ok": True,
        "manifest_sha256": source["manifest_sha256"],
        "file_count": source["file_count"],
    }


def verify_local_source(
    descriptor: Mapping[str, Any], root: Path = ROOT, run: Run = _run
) -> dict[str, Any]:
    source = descriptor["source"]
    if run(["git", "-C", str(root), "status", "--porcelain"]):
        raise ContractViolation("Git source closure mismatch")
    commit_sha = run(["git", "-C", str(root), "rev-parse", "HEAD"]).strip()
    tree_sha = run(["git", "-C", str(root), "rev-parse", "HEAD^{tree}"]).strip()
    seal = seal_source(root)
    if (
        commit_sha != source["commit_sha"]
        or tree_sha != source["tree_sha"]
        or any(
            seal[key] != source[key]
            for key in (
                "archive_sha256",
                "archive_md5",
                "manifest_sha256",
                "file_count",
            )
        )
    ):
        raise ContractViolation("Git source closure mismatch")
    return {
        "schema": "sapphire/local-source/v1",
        "ok": True,
        "commit_sha": commit_sha,
        "tree_sha": tree_sha,
        "archive_sha256": seal["archive_sha256"],
    }


def _container(
    service: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
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


def _normalize_provider_traffic(
    value: Any,
    *,
    ready_revision: Any,
) -> list[dict[str, Any]]:
    """Close Cloud Run's equivalent traffic records to one exact target.

    Cloud Run may annotate a resolved latest target with
    ``latestRevision: true`` even though ``revisionName`` already identifies
    the concrete ready revision. Explicit traffic may instead pin an older
    serving revision. The release contract stores only the concrete identity.
    Tags, unresolved latest targets, split allocations, duplicate targets, and
    provider extensions remain inadmissible.
    """
    if (
        not isinstance(ready_revision, str)
        or not ready_revision
        or ready_revision.strip() != ready_revision
        or len(ready_revision) > 128
        or not isinstance(value, list)
        or len(value) != 1
        or not isinstance(value[0], Mapping)
    ):
        raise ContractViolation("traffic projection mismatch")
    record = value[0]
    keys = set(record)
    revision_name = record.get("revisionName")
    if keys == {"percent", "revisionName"}:
        pass
    elif keys == {"latestRevision", "percent", "revisionName"}:
        if (
            record.get("latestRevision") is not True
            or revision_name != ready_revision
        ):
            raise ContractViolation("traffic projection mismatch")
    else:
        raise ContractViolation("traffic projection mismatch")
    if (
        type(record.get("percent")) is not int
        or record["percent"] != 100
        or not isinstance(revision_name, str)
        or not revision_name
        or revision_name.strip() != revision_name
        or len(revision_name) > 128
    ):
        raise ContractViolation("traffic projection mismatch")
    return [{"percent": 100, "revisionName": revision_name}]


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
    if (
        not isinstance(ready, str)
        or not ready
        or not isinstance(created, str)
        or not created
    ):
        raise ContractViolation("revision projection mismatch")
    traffic = _normalize_provider_traffic(
        status.get("traffic"),
        ready_revision=ready,
    )
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
        "resource_version": metadata.get("resourceVersion"),
        "observed_generation": status.get("observedGeneration"),
        "ready_revision": ready,
        "ready_image_digest": _nested(ready_record, "status", "imageDigest"),
        "created_revision": created,
        "created_image_digest": _nested(created_record, "status", "imageDigest"),
        "traffic": traffic,
        "iam_sha256": _iam_sha256(policy),
        "service_account": template_spec.get("serviceAccountName"),
        "environment": environment_commitments(container.get("env")),
        "service_url": service_url,
        "build_endpoint_status": build_status,
    }


def artifact_hashes(root: Path = ROOT) -> dict[str, str]:
    return {name: sha256_file(root / name) for name in sorted(REQUIRED_ARTIFACTS)}


def _require_keys(value: Mapping[str, Any], expected: set[str]) -> None:
    if set(value) != expected:
        raise ContractViolation("descriptor mismatch")


def _require_surface(value: Any, entrypoint_url: str) -> None:
    if not isinstance(value, Mapping):
        raise ContractViolation("descriptor mismatch")
    _require_keys(
        value,
        {
            "entrypoint_url",
            "entrypoint_sha256",
            "asset_count",
            "manifest_sha256",
        },
    )
    if (
        value["entrypoint_url"] != entrypoint_url
        or HEX64.fullmatch(str(value["entrypoint_sha256"])) is None
        or not isinstance(value["asset_count"], int)
        or value["asset_count"] <= 0
        or HEX64.fullmatch(str(value["manifest_sha256"])) is None
    ):
        raise ContractViolation("descriptor mismatch")


def _require_environment_commitment(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ContractViolation("descriptor mismatch")
    _require_keys(value, {"key_count", "names_sha256", "full_sha256"})
    if (
        not isinstance(value["key_count"], int)
        or value["key_count"] <= 0
        or HEX64.fullmatch(str(value["names_sha256"])) is None
        or HEX64.fullmatch(str(value["full_sha256"])) is None
    ):
        raise ContractViolation("descriptor mismatch")


def _is_image_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(
            r"[a-z0-9.-]+/[A-Za-z0-9._/-]+@sha256:[0-9a-f]{64}",
            value,
        )
        is not None
    )


def _require_descriptor_shape(descriptor: Mapping[str, Any]) -> None:
    _require_keys(
        descriptor,
        {"schema", "target", "source", "precondition", "postcondition", "artifacts"},
    )
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
    _require_keys(
        target,
        {"project", "region", "service", "service_account", "image_repository"},
    )
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
    _require_keys(
        source,
        {
            "commit_sha",
            "tree_sha",
            "archive_sha256",
            "archive_md5",
            "manifest_sha256",
            "file_count",
            "bucket",
            "object",
            "generation",
            "bucket_resource_sha256",
            "bucket_iam_sha256",
            "project_number",
        },
    )
    if HEX40_OR_64.fullmatch(str(source.get("commit_sha", ""))) is None:
        raise ContractViolation("source identity mismatch")
    if HEX40_OR_64.fullmatch(str(source.get("tree_sha", ""))) is None:
        raise ContractViolation("source identity mismatch")
    for key in ("archive_sha256", "manifest_sha256"):
        if HEX64.fullmatch(str(source.get(key, ""))) is None:
            raise ContractViolation("source identity mismatch")
    if HEX32.fullmatch(str(source.get("archive_md5", ""))) is None:
        raise ContractViolation("source identity mismatch")
    if not isinstance(source.get("file_count"), int) or source["file_count"] <= 0:
        raise ContractViolation("source identity mismatch")
    if source.get("bucket") != STAGING_BUCKET:
        raise ContractViolation("staging target mismatch")
    if not isinstance(source.get("generation"), int) or source["generation"] <= 0:
        raise ContractViolation("source generation mismatch")
    object_name = source.get("object")
    if (
        not isinstance(object_name, str)
        or object_name != f"source/sapphire/{source['archive_sha256']}.tar.gz"
    ):
        raise ContractViolation("source object mismatch")
    if source.get("project_number") != PROJECT_NUMBER:
        raise ContractViolation("bucket contract mismatch")
    if any(
        HEX64.fullmatch(str(source.get(key, ""))) is None
        for key in ("bucket_resource_sha256", "bucket_iam_sha256")
    ):
        raise ContractViolation("bucket contract mismatch")
    _require_keys(
        precondition,
        {
            "generation",
            "resource_version",
            "observed_generation",
            "ready_revision",
            "ready_image_digest",
            "created_revision",
            "created_image_digest",
            "traffic",
            "iam_sha256",
            "service_account",
            "environment",
            "service_url",
            "build_endpoint_status",
        },
    )
    if (
        not isinstance(precondition["generation"], int)
        or not isinstance(precondition["resource_version"], str)
        or not precondition["resource_version"]
        or not isinstance(precondition["observed_generation"], int)
        or precondition["observed_generation"] != precondition["generation"]
        or not isinstance(precondition["ready_revision"], str)
        or not isinstance(precondition["created_revision"], str)
        or not isinstance(precondition["build_endpoint_status"], int)
        or not _is_image_digest(precondition["ready_image_digest"])
        or not _is_image_digest(precondition["created_image_digest"])
        or HEX64.fullmatch(str(precondition["iam_sha256"])) is None
        or precondition["service_account"] != SERVICE_ACCOUNT
        or not isinstance(precondition["service_url"], str)
        or not precondition["service_url"].startswith("https://")
    ):
        raise ContractViolation("descriptor mismatch")
    try:
        normalized_traffic = _normalize_provider_traffic(
            precondition["traffic"],
            ready_revision=precondition["ready_revision"],
        )
    except ContractViolation:
        raise ContractViolation("descriptor mismatch") from None
    if precondition["traffic"] != normalized_traffic:
        raise ContractViolation("descriptor mismatch")
    _require_environment_commitment(precondition["environment"])
    _require_keys(
        postcondition,
        {
            "iam_sha256",
            "service_account",
            "environment",
            "service_url",
            "build_identity",
        },
    )
    build_identity = postcondition["build_identity"]
    if (
        postcondition["iam_sha256"] != precondition["iam_sha256"]
        or postcondition["service_account"] != SERVICE_ACCOUNT
        or postcondition["service_url"] != precondition["service_url"]
    ):
        raise ContractViolation("descriptor mismatch")
    _require_environment_commitment(postcondition["environment"])
    if not isinstance(build_identity, Mapping):
        raise ContractViolation("descriptor mismatch")
    _require_keys(build_identity, {"schema", "source_sha", "surfaces"})
    if (
        build_identity["schema"] != 1
        or build_identity["source_sha"] != source["commit_sha"]
        or not isinstance(build_identity["surfaces"], Mapping)
    ):
        raise ContractViolation("descriptor mismatch")
    surfaces = build_identity["surfaces"]
    _require_keys(surfaces, {"operator", "public"})
    _require_surface(surfaces["operator"], "/dashboard")
    _require_surface(surfaces["public"], "/")


def encode_descriptor(raw: bytes) -> str:
    encoded = base64.b64encode(zlib.compress(raw, level=9)).decode("ascii")
    if len(encoded.encode("ascii")) > MAX_SUBSTITUTION_BYTES:
        raise ContractViolation("descriptor substitution exceeds provider limit")
    return encoded


def decode_descriptor(encoded: str, expected_sha256: str) -> dict[str, Any]:
    if HEX64.fullmatch(expected_sha256) is None:
        raise ContractViolation("descriptor digest mismatch")
    if len(encoded.encode("ascii", errors="ignore")) > MAX_SUBSTITUTION_BYTES:
        raise ContractViolation("descriptor substitution exceeds provider limit")
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


def bucket_contract(run: Run = _run) -> tuple[dict[str, Any], dict[str, Any]]:
    bucket = _json_command(
        run,
        _gcloud(
            "storage",
            "buckets",
            "describe",
            f"gs://{STAGING_BUCKET}",
            "--raw",
            "--format=json",
            region=False,
        ),
    )
    policy = _json_command(
        run,
        _gcloud(
            "storage",
            "buckets",
            "get-iam-policy",
            f"gs://{STAGING_BUCKET}",
            "--format=json",
            region=False,
        ),
    )
    if (
        bucket.get("name") != STAGING_BUCKET
        or str(bucket.get("projectNumber")) != PROJECT_NUMBER
    ):
        raise ContractViolation("bucket contract mismatch")
    return bucket, policy


def verify_bucket_and_object(
    descriptor: Mapping[str, Any],
    run: Run = _run,
    read_bytes: ReadBytes = _run_bytes,
) -> dict[str, str]:
    source = descriptor["source"]
    bucket, policy = bucket_contract(run)
    if (
        sha256_bytes(canonical(bucket)) != source["bucket_resource_sha256"]
        or sha256_bytes(canonical(policy)) != source["bucket_iam_sha256"]
    ):
        raise ContractViolation("bucket contract mismatch")
    uri = f"gs://{STAGING_BUCKET}/{source['object']}#{source['generation']}"
    obj = _json_command(
        run,
        _gcloud(
            "storage",
            "objects",
            "describe",
            uri,
            "--raw",
            "--format=json",
            region=False,
        ),
    )
    archive = read_bytes(_gcloud("storage", "cat", uri, region=False))
    try:
        remote_md5 = _decode_digest(str(obj.get("md5Hash", ""))).hex()
    except (ValueError, binascii.Error):
        remote_md5 = ""
    if (
        obj.get("bucket") not in (None, STAGING_BUCKET)
        or obj.get("name") != source["object"]
        or int(obj.get("generation", 0)) != source["generation"]
        or remote_md5 != source["archive_md5"]
        or hashlib.md5(archive, usedforsecurity=False).hexdigest()
        != source["archive_md5"]
        or sha256_bytes(archive) != source["archive_sha256"]
    ):
        raise ContractViolation("source object contract mismatch")
    return {"bucket": STAGING_BUCKET, "object_generation": str(source["generation"])}


def draft_descriptor(
    object_name: str,
    generation: int,
    root: Path = ROOT,
    run: Run = _run,
    fetch: Fetch = fetch_http,
    read_bytes: ReadBytes = _run_bytes,
    operator_surface: Path | None = None,
    public_surface: Path | None = None,
) -> dict[str, Any]:
    if run(["git", "-C", str(root), "status", "--porcelain"]):
        raise ContractViolation("Git source closure mismatch")
    seal = seal_source(root)
    bucket, policy = bucket_contract(run)
    precondition = live_snapshot(run, fetch)
    service = _json_command(
        run, _gcloud("run", "services", "describe", SERVICE, "--format=json")
    )
    metadata = service.get("metadata")
    _, container = _container(service)
    if (
        not isinstance(metadata, Mapping)
        or metadata.get("generation") != precondition["generation"]
        or metadata.get("resourceVersion") != precondition["resource_version"]
    ):
        raise ContractViolation("remote state mismatch")
    descriptor = {
        "schema": SCHEMA,
        "target": {
            "project": PROJECT,
            "region": REGION,
            "service": SERVICE,
            "service_account": SERVICE_ACCOUNT,
            "image_repository": IMAGE_REPOSITORY,
        },
        "source": {
            "commit_sha": run(["git", "-C", str(root), "rev-parse", "HEAD"]).strip(),
            "tree_sha": run(
                ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"]
            ).strip(),
            "archive_sha256": seal["archive_sha256"],
            "archive_md5": seal["archive_md5"],
            "manifest_sha256": seal["manifest_sha256"],
            "file_count": seal["file_count"],
            "bucket": STAGING_BUCKET,
            "object": object_name,
            "generation": generation,
            "bucket_resource_sha256": sha256_bytes(canonical(bucket)),
            "bucket_iam_sha256": sha256_bytes(canonical(policy)),
            "project_number": PROJECT_NUMBER,
        },
        "precondition": precondition,
        "postcondition": {
            "iam_sha256": precondition["iam_sha256"],
            "service_account": SERVICE_ACCOUNT,
            "environment": environment_commitments(
                projected_environment(container.get("env"))
            ),
            "service_url": precondition["service_url"],
            "build_identity": {
                "schema": 1,
                "source_sha": run(
                    ["git", "-C", str(root), "rev-parse", "HEAD"]
                ).strip(),
                "surfaces": {
                    "operator": surface_manifest(
                        operator_surface or root / "frontend/dist", "/dashboard"
                    ),
                    "public": surface_manifest(public_surface or root / "web/out", "/"),
                },
            },
        },
        "artifacts": artifact_hashes(root),
    }
    _require_descriptor_shape(descriptor)
    verify_local_source(descriptor, root, run)
    verify_bucket_and_object(descriptor, run, read_bytes)
    encode_descriptor(canonical(descriptor))
    return descriptor


def verify_predeploy_cas(
    descriptor: Mapping[str, Any],
    run: Run = _run,
    fetch: Fetch = fetch_http,
) -> dict[str, Any]:
    try:
        current = live_snapshot(run, fetch)
    except ContractViolation:
        raise ContractViolation("remote state mismatch") from None
    if current != descriptor.get("precondition"):
        raise ContractViolation("remote state mismatch")
    return {
        "schema": "sapphire/predeploy-cas/v1",
        "ok": True,
        "precondition_sha256": sha256_bytes(canonical(descriptor["precondition"])),
    }


def prepare_service_replacement(
    service: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    image: str,
) -> dict[str, Any]:
    if (
        not image.startswith(f"{IMAGE_REPOSITORY}@sha256:")
        or HEX64.fullmatch(image.rsplit(":", 1)[-1]) is None
    ):
        raise ContractViolation("immutable image mismatch")
    metadata = service.get("metadata")
    spec = service.get("spec")
    status = service.get("status")
    if (
        not isinstance(metadata, Mapping)
        or not isinstance(spec, Mapping)
        or not isinstance(status, Mapping)
    ):
        raise ContractViolation("service projection mismatch")
    if (
        metadata.get("resourceVersion")
        != descriptor["precondition"]["resource_version"]
        or metadata.get("generation") != descriptor["precondition"]["generation"]
    ):
        raise ContractViolation("remote state mismatch")
    try:
        current_traffic = _normalize_provider_traffic(
            status.get("traffic"),
            ready_revision=status.get("latestReadyRevisionName"),
        )
    except ContractViolation:
        raise ContractViolation("remote state mismatch") from None
    if current_traffic != descriptor["precondition"]["traffic"]:
        raise ContractViolation("remote state mismatch")
    annotations = metadata.get("annotations", {})
    if not isinstance(annotations, Mapping):
        raise ContractViolation("service projection mismatch")
    writable_annotations = {
        key: copy.deepcopy(value)
        for key, value in annotations.items()
        if key
        not in {
            "run.googleapis.com/operation-id",
            "serving.knative.dev/creator",
            "serving.knative.dev/lastModifier",
        }
    }
    replacement: dict[str, Any] = {
        "apiVersion": service.get("apiVersion", "serving.knative.dev/v1"),
        "kind": service.get("kind", "Service"),
        "metadata": {
            key: copy.deepcopy(metadata[key])
            for key in ("name", "namespace", "labels", "resourceVersion")
            if key in metadata
        },
        "spec": copy.deepcopy(spec),
    }
    if writable_annotations:
        replacement["metadata"]["annotations"] = writable_annotations
    replacement["metadata"].setdefault("name", SERVICE)
    replacement["metadata"].setdefault("namespace", PROJECT_NUMBER)
    template_spec, container = _container(replacement)
    container["image"] = image
    container["env"] = projected_environment(container.get("env"))
    if template_spec.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise ContractViolation("service account mismatch")
    replacement["spec"]["traffic"] = [{"latestRevision": True, "percent": 100}]
    return replacement


def _replace_service_http(
    service: Mapping[str, Any], run: Run = _run
) -> dict[str, Any]:
    token = run(["gcloud", "auth", "print-access-token"]).strip()
    if not token or any(character.isspace() for character in token):
        raise ContractViolation("provider authorization mismatch")
    name = quote(f"namespaces/{PROJECT}/services/{SERVICE}", safe="/")
    url = f"https://{REGION}-run.googleapis.com/apis/serving.knative.dev/v1/{name}"
    request = Request(
        url,
        data=json.dumps(service, separators=(",", ":")).encode(),
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "sapphire-release-guard/1",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed provider API
            payload = json.loads(response.read())
    except HTTPError as error:
        error.read()
        raise ContractViolation("provider compare-and-swap rejected") from None
    if not isinstance(payload, dict):
        raise ContractViolation("provider compare-and-swap rejected")
    return payload


def deploy_with_provider_cas(
    descriptor: Mapping[str, Any],
    image: str,
    run: Run = _run,
    fetch: Fetch = fetch_http,
    replace: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    verify_predeploy_cas(descriptor, run, fetch)
    service = _json_command(
        run, _gcloud("run", "services", "describe", SERVICE, "--format=json")
    )
    replacement = prepare_service_replacement(service, descriptor, image)
    response = (
        replace(replacement)
        if replace is not None
        else _replace_service_http(replacement, run)
    )
    metadata = response.get("metadata") if isinstance(response, Mapping) else None
    new_resource_version = (
        metadata.get("resourceVersion") if isinstance(metadata, Mapping) else None
    )
    if (
        not isinstance(metadata, Mapping)
        or metadata.get("name") != SERVICE
        or not isinstance(new_resource_version, str)
        or not new_resource_version
        or new_resource_version == descriptor["precondition"]["resource_version"]
    ):
        raise ContractViolation("provider compare-and-swap rejected")
    return {
        "schema": "sapphire/provider-cas/v1",
        "ok": True,
        "image_sha256": sha256_bytes(image.encode()),
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
    build_source = build.get("source")
    provenance = build.get("sourceProvenance")
    if (
        not isinstance(build_source, Mapping)
        or set(build_source) != {"storageSource"}
        or not isinstance(provenance, Mapping)
        or set(provenance) != {"fileHashes", "resolvedStorageSource"}
        or not isinstance(submitted, Mapping)
        or set(submitted) != {"bucket", "object", "generation"}
        or not isinstance(resolved, Mapping)
        or set(resolved) != {"bucket", "object", "generation"}
    ):
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
    file_hashes = provenance["fileHashes"]
    exact_key = f"gs://{source['bucket']}/{source['object']}#{source['generation']}"
    if (
        submitted_projection != expected_storage
        or resolved_projection != expected_storage
        or not isinstance(file_hashes, Mapping)
        or set(file_hashes) != {exact_key}
    ):
        return False
    record = file_hashes[exact_key]
    hashes = (
        record.get("fileHash")
        if isinstance(record, Mapping) and set(record) == {"fileHash"}
        else None
    )
    if not isinstance(hashes, list) or not hashes:
        return False
    observed: dict[str, bytes] = {}
    try:
        for item in hashes:
            if (
                not isinstance(item, Mapping)
                or set(item) != {"type", "value"}
                or item.get("type") not in {"SHA256", "MD5"}
                or item["type"] in observed
            ):
                return False
            observed[item["type"]] = _decode_digest(str(item["value"]))
    except (ValueError, binascii.Error):
        return False
    return (
        observed.get("SHA256") == bytes.fromhex(source["archive_sha256"])
        and set(observed).issubset({"SHA256", "MD5"})
        and (
            "MD5" not in observed
            or observed["MD5"] == bytes.fromhex(source["archive_md5"])
        )
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
        "_SOURCE_TREE_SHA": source["tree_sha"],
        "_SOURCE_ARCHIVE_SHA256": source["archive_sha256"],
        "_SOURCE_ARCHIVE_MD5": source["archive_md5"],
        "_SOURCE_FILE_COUNT": str(source["file_count"]),
        "_SOURCE_GENERATION": str(source["generation"]),
        "_SOURCE_MANIFEST_SHA256": source["manifest_sha256"],
        "_SOURCE_OBJECT": source["object"],
    }
    actual_custom = {
        key: str(value) for key, value in substitutions.items() if key.startswith("_")
    }
    encoded_descriptor = actual_custom.pop("_ACTION_DESCRIPTOR_ZLIB_B64", "")
    try:
        submitted_descriptor = decode_descriptor(encoded_descriptor, descriptor_sha256)
    except ContractViolation:
        raise ContractViolation("build substitutions mismatch") from None
    if submitted_descriptor != descriptor or actual_custom != expected_custom:
        raise ContractViolation("build substitutions mismatch")
    if build.get("images") != [f"{IMAGE_REPOSITORY}:{build_id}"]:
        raise ContractViolation("build output image mismatch")
    if require_success:
        immutable_image(build, build_id)
    return {
        "schema": "sapphire/build-provenance/v1",
        "ok": True,
        "build_id_sha256": sha256_bytes(build_id.encode()),
        "source_identity_sha256": sha256_bytes(canonical(expected_custom)),
    }


def immutable_image(build: Mapping[str, Any], build_id: str) -> str:
    images = _nested(build, "results", "images")
    if not isinstance(images, list) or len(images) != 2:
        raise ContractViolation("build output image mismatch")
    names: set[str] = set()
    digests: set[str] = set()
    for image in images:
        if not isinstance(image, Mapping) or set(image) != {
            "artifactRegistryPackage",
            "digest",
            "name",
            "pushTiming",
        }:
            raise ContractViolation("build output image mismatch")
        digest = image["digest"]
        timing = image["pushTiming"]
        expected_package = (
            "projects/sapphire-479610/locations/us/repositories/gcr.io/"
            f"packages/sapphire-alpha-dashboard/versions/{digest}"
        )
        if (
            not isinstance(digest, str)
            or not digest.startswith("sha256:")
            or HEX64.fullmatch(digest.removeprefix("sha256:")) is None
            or image["artifactRegistryPackage"] != expected_package
            or not isinstance(timing, Mapping)
            or set(timing) != {"startTime", "endTime"}
            or not all(isinstance(value, str) and value for value in timing.values())
        ):
            raise ContractViolation("build output image mismatch")
        names.add(str(image["name"]))
        digests.add(digest)
    if (
        names != {IMAGE_REPOSITORY, f"{IMAGE_REPOSITORY}:{build_id}"}
        or len(digests) != 1
    ):
        raise ContractViolation("build output image mismatch")
    digest = digests.pop()
    return f"{IMAGE_REPOSITORY}@{digest}"


def verify_registry_digest(
    build_id: str, immutable: str, run: Run = _run
) -> dict[str, Any]:
    record = _json_command(
        run,
        _gcloud(
            "container",
            "images",
            "describe",
            f"{IMAGE_REPOSITORY}:{build_id}",
            "--format=json",
            region=False,
        ),
    )
    summary = record.get("image_summary")
    expected = {
        "digest": immutable.removeprefix(f"{IMAGE_REPOSITORY}@"),
        "fully_qualified_digest": immutable,
        "registry": "gcr.io",
        "repository": "sapphire-479610/sapphire-alpha-dashboard",
    }
    if (
        set(record) != {"image_summary"}
        or not isinstance(summary, Mapping)
        or dict(summary) != expected
    ):
        raise ContractViolation("registry image mismatch")
    return {
        "schema": "sapphire/registry-readback/v1",
        "ok": True,
        "immutable_image_sha256": sha256_bytes(immutable.encode()),
    }


def _exact_build_identity(
    payload: Any,
    expected: Mapping[str, Any],
    build_id: str,
    revision: str,
) -> bool:
    if not isinstance(payload, Mapping):
        return False
    return payload == {
        "schema": 1,
        "source_sha": expected["source_sha"],
        "build_id": build_id,
        "runtime_service": SERVICE,
        "runtime_revision": revision,
        "surfaces": expected["surfaces"],
        "complete": True,
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
    try:
        current = live_snapshot(run, fetch)
    except ContractViolation:
        raise ContractViolation("postdeploy state mismatch") from None
    previous = descriptor["precondition"]
    expected = descriptor["postcondition"]
    ready = current["ready_revision"]
    immutable = immutable_image(build, build_id)
    build_status, build_body = fetch(f"{current['service_url']}/api/build")
    try:
        build_identity = json.loads(build_body)
    except json.JSONDecodeError:
        build_identity = None
    checks = {
        "generation_plus_one": current["generation"] == previous["generation"] + 1,
        "generation_observed": current["observed_generation"] == current["generation"],
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
        "build_endpoint_exact": build_status == 200,
        "build_identity_exact": _exact_build_identity(
            build_identity, expected["build_identity"], build_id, ready
        ),
        "output_image_exact": current["ready_image_digest"] == immutable,
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
        "_ACTION_DESCRIPTOR_ZLIB_B64": encode_descriptor(raw_descriptor),
        "_ACTION_DESCRIPTOR_SHA256": descriptor_sha256,
        "_BUILD_SHA": source["commit_sha"],
        "_SOURCE_TREE_SHA": source["tree_sha"],
        "_SOURCE_ARCHIVE_SHA256": source["archive_sha256"],
        "_SOURCE_ARCHIVE_MD5": source["archive_md5"],
        "_SOURCE_FILE_COUNT": str(source["file_count"]),
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

    workspace = commands.add_parser("verify-workspace")
    workspace.add_argument("--descriptor-zlib-b64", required=True)
    workspace.add_argument("--descriptor-sha256", required=True)

    post = commands.add_parser("postdeploy")
    post.add_argument("--descriptor-zlib-b64", required=True)
    post.add_argument("--descriptor-sha256", required=True)
    post.add_argument("--build-id", required=True)
    args = parser.parse_args()

    if args.command == "local-preflight":

        def execute_local() -> dict[str, Any]:
            descriptor, _ = load_descriptor(args.descriptor, args.descriptor_sha256)
            verify_artifacts(descriptor)
            verify_local_source(descriptor)
            verify_bucket_and_object(descriptor)
            return verify_predeploy_cas(descriptor)

        return _safe_main(execute_local)

    if args.command == "render-cloudbuild":

        def execute_render() -> dict[str, Any]:
            descriptor, raw = load_descriptor(args.descriptor, args.descriptor_sha256)
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

    descriptor = decode_descriptor(args.descriptor_zlib_b64, args.descriptor_sha256)
    if args.command == "verify-workspace":
        return _safe_main(
            lambda: (
                verify_artifacts(descriptor),
                verify_workspace(descriptor),
            )[1]
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
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())

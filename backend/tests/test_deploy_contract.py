"""Hostile goldens for the content-addressed release guard."""

from __future__ import annotations

import base64
import copy
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import tarfile
from urllib.error import HTTPError
import zlib

import pytest

from scripts import deploy_contract as guard


SENTINEL = "never-emit-runtime-canary"
READY = "sapphire-alpha-dashboard-00073-kv2"
CREATED = "sapphire-alpha-dashboard-00074-p42"
OLDER = "sapphire-alpha-dashboard-00072-old"
READY_DIGEST = guard.IMAGE_REPOSITORY + "@sha256:" + "a" * 64
CREATED_DIGEST = guard.IMAGE_REPOSITORY + "@sha256:" + "b" * 64
SOURCE_SHA = "c" * 40
TREE_SHA = "1" * 40
ARCHIVE_SHA = "d" * 64
ARCHIVE_MD5 = "2" * 32
MANIFEST_SHA = "e" * 64


def _environment() -> list[dict]:
    return [
        {"name": "AUTH_PASSWORD", "value": SENTINEL},
        {"name": "AUTH_USERNAME", "value": "sapphire"},
        {"name": "PUBLIC_READ_ONLY", "value": "1"},
        {
            "name": "TELEMETRY_INGEST_SECRET",
            "valueFrom": {"secretKeyRef": {"name": "secret", "key": "latest"}},
        },
    ]


def _policy() -> dict:
    return {
        "bindings": [{"members": ["allUsers"], "role": "roles/run.invoker"}],
        "version": 1,
        "etag": "ignored",
    }


def _service(environment: list[dict] | None = None) -> dict:
    return {
        "metadata": {"generation": 82, "resourceVersion": "AAXY-example"},
        "spec": {
            "template": {
                "spec": {
                    "containers": [{"env": environment or _environment()}],
                    "serviceAccountName": guard.SERVICE_ACCOUNT,
                }
            }
        },
        "status": {
            "latestCreatedRevisionName": CREATED,
            "latestReadyRevisionName": READY,
            "observedGeneration": 82,
            "traffic": [{"percent": 100, "revisionName": READY}],
            "url": "https://service.example.test",
        },
    }


def _runner(
    *,
    service: dict | None = None,
    policy: dict | None = None,
    build: dict | None = None,
):
    service = service or _service()
    policy = policy or _policy()

    def run(argv):
        command = " ".join(argv)
        if "builds describe" in command:
            assert build is not None
            return json.dumps(build)
        if "get-iam-policy" in command:
            return json.dumps(policy)
        if f"revisions describe {READY}" in command:
            return json.dumps(
                {"metadata": {"name": READY}, "status": {"imageDigest": READY_DIGEST}}
            )
        if f"revisions describe {CREATED}" in command:
            return json.dumps(
                {
                    "metadata": {"name": CREATED},
                    "status": {"imageDigest": CREATED_DIGEST},
                }
            )
        if "services describe" in command:
            return json.dumps(service)
        raise AssertionError(command)

    return run


def _fetch(url: str) -> tuple[int, str]:
    if url.endswith("/api/build"):
        return 404, '{"detail":"not found"}'
    raise AssertionError(url)


@pytest.mark.parametrize(
    "provider_traffic",
    [
        [{"percent": 100, "revisionName": READY}],
        [{"percent": 100, "revisionName": OLDER}],
        [{"latestRevision": True, "percent": 100, "revisionName": READY}],
    ],
)
def test_live_snapshot_normalizes_supported_provider_traffic(provider_traffic):
    service = _service()
    service["status"]["traffic"] = provider_traffic

    snapshot = guard.live_snapshot(_runner(service=service), _fetch)

    assert snapshot["traffic"] == [
        {
            "percent": 100,
            "revisionName": provider_traffic[0]["revisionName"],
        }
    ]


@pytest.mark.parametrize(
    "provider_traffic",
    [
        [],
        [
            {"percent": 50, "revisionName": READY},
            {"percent": 50, "revisionName": CREATED},
        ],
        [
            {"percent": 50, "revisionName": READY},
            {"percent": 50, "revisionName": READY},
        ],
        [{"percent": 99, "revisionName": READY}],
        [{"percent": True, "revisionName": READY}],
        [{"percent": 100}],
        [{"latestRevision": True, "percent": 100}],
        [{"latestRevision": False, "percent": 100, "revisionName": READY}],
        [{"latestRevision": True, "percent": 100, "revisionName": CREATED}],
        [{"percent": 100, "revisionName": ""}],
        [{"percent": 100, "revisionName": None}],
        [{"percent": 100, "revisionName": READY, "tag": "prod"}],
        [{"percent": 100, "revisionName": READY, "url": "https://tag.invalid"}],
        ["not-a-traffic-record"],
    ],
)
def test_live_snapshot_rejects_ambiguous_or_open_traffic(provider_traffic):
    service = _service()
    service["status"]["traffic"] = provider_traffic

    with pytest.raises(guard.ContractViolation, match="traffic projection mismatch"):
        guard.live_snapshot(_runner(service=service), _fetch)


def _descriptor() -> dict:
    precondition = guard.live_snapshot(_runner(), _fetch)
    return {
        "schema": guard.SCHEMA,
        "target": {
            "project": guard.PROJECT,
            "region": guard.REGION,
            "service": guard.SERVICE,
            "service_account": guard.SERVICE_ACCOUNT,
            "image_repository": guard.IMAGE_REPOSITORY,
        },
        "source": {
            "commit_sha": SOURCE_SHA,
            "tree_sha": TREE_SHA,
            "archive_sha256": ARCHIVE_SHA,
            "archive_md5": ARCHIVE_MD5,
            "manifest_sha256": MANIFEST_SHA,
            "file_count": 200,
            "bucket": guard.STAGING_BUCKET,
            "object": f"source/sapphire/{ARCHIVE_SHA}.tar.gz",
            "generation": 123456,
            "bucket_resource_sha256": "f" * 64,
            "bucket_iam_sha256": "3" * 64,
            "project_number": guard.PROJECT_NUMBER,
        },
        "precondition": precondition,
        "postcondition": {
            "iam_sha256": precondition["iam_sha256"],
            "service_account": precondition["service_account"],
            "environment": precondition["environment"],
            "service_url": precondition["service_url"],
            "build_identity": {
                "schema": 1,
                "source_sha": SOURCE_SHA,
                "surfaces": {
                    "operator": {
                        "entrypoint_url": "/dashboard",
                        "entrypoint_sha256": "4" * 64,
                        "asset_count": 10,
                        "manifest_sha256": "5" * 64,
                    },
                    "public": {
                        "entrypoint_url": "/",
                        "entrypoint_sha256": "6" * 64,
                        "asset_count": 20,
                        "manifest_sha256": "7" * 64,
                    },
                },
            },
        },
        "artifacts": guard.artifact_hashes(),
    }


def _build_record(descriptor: dict, descriptor_sha: str) -> dict:
    source = descriptor["source"]
    storage = {
        "bucket": source["bucket"],
        "object": source["object"],
        "generation": str(source["generation"]),
    }
    exact_key = f"gs://{source['bucket']}/{source['object']}#{source['generation']}"
    archive_b64 = base64.urlsafe_b64encode(bytes.fromhex(ARCHIVE_SHA)).decode()
    archive_md5_b64 = base64.urlsafe_b64encode(bytes.fromhex(ARCHIVE_MD5)).decode()
    return {
        "id": "build-123",
        "status": "SUCCESS",
        "source": {"storageSource": copy.deepcopy(storage)},
        "sourceProvenance": {
            "resolvedStorageSource": copy.deepcopy(storage),
            "fileHashes": {
                exact_key: {
                    "fileHash": [
                        {"type": "MD5", "value": archive_md5_b64},
                        {"type": "SHA256", "value": archive_b64},
                    ]
                }
            },
        },
        "substitutions": {
            "_ACTION_DESCRIPTOR_ZLIB_B64": base64.b64encode(
                zlib.compress(guard.canonical(descriptor), level=9)
            ).decode(),
            "_ACTION_DESCRIPTOR_SHA256": descriptor_sha,
            "_BUILD_SHA": SOURCE_SHA,
            "_SOURCE_TREE_SHA": TREE_SHA,
            "_SOURCE_ARCHIVE_SHA256": ARCHIVE_SHA,
            "_SOURCE_ARCHIVE_MD5": ARCHIVE_MD5,
            "_SOURCE_FILE_COUNT": str(source["file_count"]),
            "_SOURCE_GENERATION": str(source["generation"]),
            "_SOURCE_MANIFEST_SHA256": MANIFEST_SHA,
            "_SOURCE_OBJECT": source["object"],
        },
        "images": [f"{guard.IMAGE_REPOSITORY}:build-123"],
        "results": {
            "images": [
                {
                    "digest": "sha256:" + "9" * 64,
                    "name": guard.IMAGE_REPOSITORY,
                    "artifactRegistryPackage": (
                        "projects/sapphire-479610/locations/us/repositories/gcr.io/"
                        "packages/sapphire-alpha-dashboard/versions/sha256:" + "9" * 64
                    ),
                    "pushTiming": {"startTime": "start", "endTime": "end"},
                },
                {
                    "digest": "sha256:" + "9" * 64,
                    "name": f"{guard.IMAGE_REPOSITORY}:build-123",
                    "artifactRegistryPackage": (
                        "projects/sapphire-479610/locations/us/repositories/gcr.io/"
                        "packages/sapphire-alpha-dashboard/versions/sha256:" + "9" * 64
                    ),
                    "pushTiming": {"startTime": "start", "endTime": "end"},
                },
            ]
        },
    }


def test_real_http_error_404_is_observed(monkeypatch):
    error = HTTPError(
        "https://service.example.test/api/build",
        404,
        "not found",
        {},
        BytesIO(b'{"detail":"not found"}'),
    )
    monkeypatch.setattr(
        guard, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(error)
    )
    assert guard.fetch_http("https://service.example.test/api/build") == (
        404,
        '{"detail":"not found"}',
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda service, policy: service["metadata"].update(generation=83),
        lambda service, policy: service["status"].update(observedGeneration=83),
        lambda service, policy: service["status"].update(
            latestReadyRevisionName=CREATED
        ),
        lambda service, policy: service["status"].update(
            traffic=[{"percent": 99, "revisionName": READY}]
        ),
        lambda service, policy: service["spec"]["template"]["spec"].update(
            serviceAccountName="other@example.invalid"
        ),
        lambda service, policy: policy["bindings"].append(
            {"members": ["user:other@example.invalid"], "role": "roles/run.admin"}
        ),
        lambda service, policy: service["spec"]["template"]["spec"]["containers"][0][
            "env"
        ][0].update(value=SENTINEL + "-changed"),
    ],
)
def test_predeploy_cas_fails_closed_for_every_remote_drift_without_echo(mutate):
    descriptor = _descriptor()
    service = _service()
    policy = _policy()
    mutate(service, policy)
    with pytest.raises(guard.ContractViolation) as error:
        guard.verify_predeploy_cas(
            descriptor,
            run=_runner(service=service, policy=policy),
            fetch=_fetch,
        )
    assert str(error.value) == "remote state mismatch"
    assert SENTINEL not in str(error.value)


def test_combined_source_and_remote_drift_never_reaches_a_mutation():
    descriptor = _descriptor()
    build = _build_record(descriptor, "1" * 64)
    build["source"]["storageSource"].pop("generation")
    service = _service()
    service["status"]["traffic"] = [{"percent": 50, "revisionName": READY}]
    assert guard.source_provenance_exact(build, descriptor) is False
    with pytest.raises(guard.ContractViolation, match="remote state mismatch"):
        guard.verify_predeploy_cas(descriptor, _runner(service=service), _fetch)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_submitted_generation",
        "wrong_key",
        "extra_hash",
        "resolved_generation",
        "alternate_source",
        "extra_storage_field",
        "extra_provenance_field",
    ],
)
def test_source_provenance_requires_exact_generation_and_file_hash_key(mutation):
    descriptor = _descriptor()
    build = _build_record(descriptor, "1" * 64)
    provenance = build["sourceProvenance"]
    if mutation == "missing_submitted_generation":
        build["source"]["storageSource"].pop("generation")
    elif mutation == "wrong_key":
        value = next(iter(provenance["fileHashes"].values()))
        provenance["fileHashes"] = {"arbitrary-key": value}
    elif mutation == "extra_hash":
        provenance["fileHashes"]["extra"] = copy.deepcopy(
            next(iter(provenance["fileHashes"].values()))
        )
    elif mutation == "resolved_generation":
        provenance["resolvedStorageSource"]["generation"] = "999"
    elif mutation == "alternate_source":
        build["source"]["gitSource"] = {"url": "https://attacker.invalid/repo"}
    elif mutation == "extra_storage_field":
        build["source"]["storageSource"]["extra"] = True
    else:
        provenance["resolvedRepoSource"] = {"repoName": "attacker"}
    assert guard.source_provenance_exact(build, descriptor) is False


def test_real_cloud_build_fixture_uses_generation_key_and_urlsafe_digest():
    fixture = json.loads(
        (
            Path(__file__).parent / "fixtures" / "cloudbuild-storage-provenance.json"
        ).read_text(encoding="utf-8")
    )
    descriptor = _descriptor()
    descriptor["source"].update(
        bucket=fixture["source"]["storageSource"]["bucket"],
        object=fixture["source"]["storageSource"]["object"],
        generation=int(fixture["source"]["storageSource"]["generation"]),
        archive_sha256=fixture["expected"]["archive_sha256"],
        archive_md5=fixture["expected"]["archive_md5"],
    )
    assert guard.source_provenance_exact(fixture, descriptor) is True


def test_descriptor_schema_is_recursively_closed_and_substitution_is_bounded():
    descriptor = _descriptor()
    descriptor["source"]["attacker_extension"] = True
    with pytest.raises(guard.ContractViolation, match="descriptor mismatch"):
        guard._require_descriptor_shape(descriptor)

    descriptor = _descriptor()
    descriptor["padding"] = "x" * 10_000
    with pytest.raises(guard.ContractViolation, match="descriptor mismatch"):
        guard._require_descriptor_shape(descriptor)
    with pytest.raises(guard.ContractViolation, match="substitution"):
        guard.encode_descriptor(os.urandom(5000))


def test_descriptor_requires_normalized_explicit_revision_traffic():
    descriptor = _descriptor()
    descriptor["precondition"]["traffic"][0]["latestRevision"] = True

    with pytest.raises(guard.ContractViolation, match="descriptor mismatch"):
        guard._require_descriptor_shape(descriptor)


def test_predeploy_cas_accepts_equivalent_latest_revision_provider_record():
    descriptor = _descriptor()
    service = _service()
    service["status"]["traffic"] = [
        {"latestRevision": True, "percent": 100, "revisionName": READY}
    ]

    result = guard.verify_predeploy_cas(
        descriptor,
        run=_runner(service=service),
        fetch=_fetch,
    )

    assert result["ok"] is True


@pytest.mark.parametrize("status", ["WORKING", "QUEUED", "FAILURE", "CANCELLED"])
def test_release_build_must_be_terminal_success(status):
    descriptor = _descriptor()
    descriptor_sha = "1" * 64
    build = _build_record(descriptor, descriptor_sha)
    build["status"] = status
    with pytest.raises(guard.ContractViolation, match="build identity mismatch"):
        guard.verify_build_record(
            descriptor,
            descriptor_sha,
            "build-123",
            run=_runner(build=build),
            require_success=True,
        )


def test_build_results_require_one_digest_across_package_and_exact_build_tag():
    descriptor = _descriptor()
    build = _build_record(descriptor, "1" * 64)
    immutable = guard.immutable_image(build, "build-123")
    assert immutable.endswith("sha256:" + "9" * 64)

    build["results"]["images"][1]["digest"] = "sha256:" + "8" * 64
    with pytest.raises(guard.ContractViolation, match="build output image mismatch"):
        guard.immutable_image(build, "build-123")


def test_build_record_rejects_arbitrary_custom_substitution():
    descriptor = _descriptor()
    descriptor_sha = "1" * 64
    build = _build_record(descriptor, descriptor_sha)
    build["substitutions"]["_UNBOUND"] = "anything"
    with pytest.raises(guard.ContractViolation, match="build substitutions mismatch"):
        guard.verify_build_record(
            descriptor,
            descriptor_sha,
            "build-123",
            run=_runner(build=build),
            require_success=True,
        )


def test_postdeploy_requires_generation_plus_one_and_built_digest(monkeypatch):
    descriptor = _descriptor()
    descriptor_sha = "1" * 64
    build = _build_record(descriptor, descriptor_sha)
    digest = build["results"]["images"][0]["digest"]
    current = {
        **descriptor["precondition"],
        "generation": 83,
        "observed_generation": 83,
        "ready_revision": "sapphire-alpha-dashboard-00075-new",
        "created_revision": "sapphire-alpha-dashboard-00075-new",
        "ready_image_digest": f"{guard.IMAGE_REPOSITORY}@{digest}",
        "created_image_digest": f"{guard.IMAGE_REPOSITORY}@{digest}",
        "traffic": [
            {
                "percent": 100,
                "revisionName": "sapphire-alpha-dashboard-00075-new",
            }
        ],
        "build_endpoint_status": 200,
        "build_identity": {
            **descriptor["postcondition"]["build_identity"],
            "build_id": "build-123",
            "runtime_service": guard.SERVICE,
            "runtime_revision": "sapphire-alpha-dashboard-00075-new",
            "complete": True,
        },
    }
    monkeypatch.setattr(
        guard, "verify_build_record", lambda *_args, **_kwargs: {"ok": True}
    )
    monkeypatch.setattr(guard, "live_snapshot", lambda *_args, **_kwargs: current)

    def fetch(url):
        if url.endswith("/api/build"):
            return 200, json.dumps(current["build_identity"])
        return _fetch(url)

    result = guard.verify_postdeploy(
        descriptor,
        descriptor_sha,
        "build-123",
        run=_runner(build=build),
        fetch=fetch,
    )
    assert result["ok"] is True

    current["generation"] = 84
    with pytest.raises(guard.ContractViolation, match="postdeploy state mismatch"):
        guard.verify_postdeploy(
            descriptor,
            descriptor_sha,
            "build-123",
            run=_runner(build=build),
            fetch=fetch,
        )


def test_postdeploy_masks_invalid_provider_traffic_as_postdeploy_mismatch(monkeypatch):
    descriptor = _descriptor()
    descriptor_sha = "1" * 64
    build = _build_record(descriptor, descriptor_sha)
    monkeypatch.setattr(
        guard,
        "verify_build_record",
        lambda *_args, **_kwargs: {"ok": True},
    )
    monkeypatch.setattr(
        guard,
        "live_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            guard.ContractViolation("traffic projection mismatch")
        ),
    )

    with pytest.raises(guard.ContractViolation, match="^postdeploy state mismatch$"):
        guard.verify_postdeploy(
            descriptor,
            descriptor_sha,
            "build-123",
            run=_runner(build=build),
            fetch=_fetch,
        )


def test_artifact_binding_detects_wrapper_or_guard_mutation(tmp_path):
    for relative in guard.REQUIRED_ARTIFACTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")
    descriptor = _descriptor()
    descriptor["artifacts"] = guard.artifact_hashes(tmp_path)
    guard.verify_artifacts(descriptor, tmp_path)
    (tmp_path / "deploy.sh").write_text("changed", encoding="utf-8")
    with pytest.raises(guard.ContractViolation, match="artifact closure mismatch"):
        guard.verify_artifacts(descriptor, tmp_path)


def test_descriptor_hash_is_raw_byte_exact_and_failure_is_constant(tmp_path, capsys):
    descriptor = _descriptor()
    path = tmp_path / "action.json"
    raw = guard.canonical(descriptor)
    path.write_bytes(raw)
    assert guard.load_descriptor(path, guard.sha256_bytes(raw))[0] == descriptor
    encoded = base64.b64encode(zlib.compress(raw, level=9)).decode()
    assert len(encoded) < 4000
    assert guard.decode_descriptor(encoded, guard.sha256_bytes(raw)) == descriptor
    code = guard._safe_main(lambda: (_ for _ in ()).throw(ValueError(SENTINEL)))
    assert code == 1
    output = capsys.readouterr().out
    assert SENTINEL not in output
    assert json.loads(output)["error"] == "contract violation"


def test_git_manifest_and_archive_are_deterministic_and_byte_sensitive(
    tmp_path, monkeypatch
):
    (tmp_path / "a.txt").write_bytes(b"alpha")
    executable = tmp_path / "bin" / "run"
    executable.parent.mkdir()
    executable.write_bytes(b"#!/bin/sh\n")
    executable.chmod(0o755)

    records = [
        {"path": "a.txt", "mode": "100644"},
        {"path": "bin/run", "mode": "100755"},
    ]
    monkeypatch.setattr(guard, "tracked_files", lambda _root=tmp_path: records)
    first = guard.seal_source(tmp_path)
    second = guard.seal_source(tmp_path)
    assert first == second
    assert first["file_count"] == 2
    assert hashlib.sha256(first["archive"]).hexdigest() == first["archive_sha256"]

    (tmp_path / "a.txt").write_bytes(b"changed")
    changed = guard.seal_source(tmp_path)
    assert changed["manifest_sha256"] != first["manifest_sha256"]
    assert changed["archive_sha256"] != first["archive_sha256"]


def test_provider_replacement_carries_resource_version_and_digest_only():
    descriptor = _descriptor()
    service = _service()
    image = f"{guard.IMAGE_REPOSITORY}@sha256:{'8' * 64}"

    replacement = guard.prepare_service_replacement(service, descriptor, image)

    assert replacement["metadata"]["resourceVersion"] == "AAXY-example"
    assert "status" not in replacement
    assert replacement["spec"]["template"]["spec"]["containers"][0]["image"] == image
    assert replacement["spec"]["traffic"] == [{"latestRevision": True, "percent": 100}]
    environment = replacement["spec"]["template"]["spec"]["containers"][0]["env"]
    by_name = {item["name"]: item for item in environment}
    assert by_name["AUTH_PASSWORD"]["value"] == SENTINEL
    assert {
        name: by_name[name]["value"] for name in guard.PUBLIC_ENVIRONMENT
    } == guard.PUBLIC_ENVIRONMENT

    with pytest.raises(guard.ContractViolation, match="immutable image"):
        guard.prepare_service_replacement(
            service,
            descriptor,
            f"{guard.IMAGE_REPOSITORY}:mutable",
        )


@pytest.mark.parametrize(
    "provider_traffic",
    [
        [
            {"percent": 50, "revisionName": READY},
            {"percent": 50, "revisionName": CREATED},
        ],
        [{"latestRevision": True, "percent": 100}],
        [{"percent": 100, "revisionName": READY, "tag": "prod"}],
        [{"percent": 100, "revisionName": CREATED}],
    ],
)
def test_provider_replacement_rejects_noncanonical_current_traffic(provider_traffic):
    descriptor = _descriptor()
    service = _service()
    service["status"]["traffic"] = provider_traffic
    image = f"{guard.IMAGE_REPOSITORY}@sha256:{'8' * 64}"

    with pytest.raises(guard.ContractViolation, match="remote state mismatch"):
        guard.prepare_service_replacement(service, descriptor, image)


def test_provider_cas_requires_an_exact_new_resource_version(monkeypatch):
    descriptor = _descriptor()
    service = _service()
    image = f"{guard.IMAGE_REPOSITORY}@sha256:{'8' * 64}"
    monkeypatch.setattr(
        guard,
        "verify_predeploy_cas",
        lambda *_args, **_kwargs: {"ok": True},
    )

    for response in (
        {"metadata": {"name": guard.SERVICE}},
        {
            "metadata": {
                "name": guard.SERVICE,
                "resourceVersion": descriptor["precondition"]["resource_version"],
            }
        },
        {"metadata": {"name": "other-service", "resourceVersion": "new-version"}},
    ):
        with pytest.raises(
            guard.ContractViolation, match="provider compare-and-swap rejected"
        ):
            guard.deploy_with_provider_cas(
                descriptor,
                image,
                run=_runner(service=service),
                fetch=_fetch,
                replace=lambda _replacement, response=response: response,
            )

    result = guard.deploy_with_provider_cas(
        descriptor,
        image,
        run=_runner(service=service),
        fetch=_fetch,
        replace=lambda _replacement: {
            "metadata": {
                "name": guard.SERVICE,
                "resourceVersion": "new-version",
            }
        },
    )
    assert result["ok"] is True


def test_extracted_workspace_must_equal_the_sealed_manifest(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    extracted = tmp_path / "extracted"
    source_root.mkdir()
    extracted.mkdir()
    (source_root / "a.txt").write_bytes(b"alpha")
    records = [{"path": "a.txt", "mode": "100644"}]
    monkeypatch.setattr(guard, "tracked_files", lambda _root=source_root: records)
    sealed = guard.seal_source(source_root)
    archive = tmp_path / "source.tar.gz"
    archive.write_bytes(sealed["archive"])
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(extracted, filter="data")
    descriptor = {
        "source": {key: sealed[key] for key in ("manifest_sha256", "file_count")}
    }

    assert guard.verify_workspace(descriptor, extracted)["ok"] is True
    (extracted / "a.txt").write_bytes(b"drift")
    with pytest.raises(guard.ContractViolation, match="source manifest mismatch"):
        guard.verify_workspace(descriptor, extracted)


def test_registry_readback_must_resolve_build_tag_to_exact_digest():
    immutable = f"{guard.IMAGE_REPOSITORY}@sha256:{'8' * 64}"

    def runner(argv):
        assert f"{guard.IMAGE_REPOSITORY}:build-123" in argv
        return json.dumps(
            {
                "image_summary": {
                    "digest": "sha256:" + "8" * 64,
                    "fully_qualified_digest": immutable,
                    "registry": "gcr.io",
                    "repository": "sapphire-479610/sapphire-alpha-dashboard",
                }
            }
        )

    assert guard.verify_registry_digest("build-123", immutable, runner)["ok"] is True
    with pytest.raises(guard.ContractViolation, match="registry image mismatch"):
        guard.verify_registry_digest(
            "build-123",
            f"{guard.IMAGE_REPOSITORY}@sha256:{'9' * 64}",
            runner,
        )


def test_bucket_ownership_iam_and_generation_bytes_are_all_bound():
    descriptor = _descriptor()
    archive = b"exact staged archive bytes"
    bucket = {
        "name": guard.STAGING_BUCKET,
        "projectNumber": guard.PROJECT_NUMBER,
        "metageneration": "3",
    }
    policy = {"bindings": [{"role": "roles/storage.objectViewer"}], "etag": "abc"}
    source = descriptor["source"]
    source["archive_sha256"] = hashlib.sha256(archive).hexdigest()
    source["archive_md5"] = hashlib.md5(archive, usedforsecurity=False).hexdigest()
    source["bucket_resource_sha256"] = guard.sha256_bytes(guard.canonical(bucket))
    source["bucket_iam_sha256"] = guard.sha256_bytes(guard.canonical(policy))

    def runner(argv):
        command = " ".join(argv)
        if "buckets describe" in command:
            assert "--raw" in argv
            return json.dumps(bucket)
        if "get-iam-policy" in command:
            return json.dumps(policy)
        if "objects describe" in command:
            assert "--raw" in argv
            assert f"#{source['generation']}" in command
            return json.dumps(
                {
                    "bucket": guard.STAGING_BUCKET,
                    "name": source["object"],
                    "generation": str(source["generation"]),
                    "md5Hash": base64.urlsafe_b64encode(
                        bytes.fromhex(source["archive_md5"])
                    ).decode(),
                }
            )
        raise AssertionError(command)

    result = guard.verify_bucket_and_object(descriptor, runner, lambda _argv: archive)
    assert result["object_generation"] == str(source["generation"])

    policy["bindings"].append({"role": "roles/storage.admin"})
    with pytest.raises(guard.ContractViolation, match="bucket contract mismatch"):
        guard.verify_bucket_and_object(descriptor, runner, lambda _argv: archive)

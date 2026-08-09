"""Hostile goldens for the content-addressed release guard."""

from __future__ import annotations

import base64
import copy
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import tarfile
from urllib.error import HTTPError
import zlib

import pytest

from scripts import deploy_contract as guard
from scripts import trusted_release as launcher


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
            "name": "MOSS_TELEMETRY_INGEST_SECRET",
            "valueFrom": {
                "secretKeyRef": {
                    "name": "sapphire-moss-telemetry-ingest",
                    "key": "1",
                }
            },
        },
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


def _descriptor(environment: list[dict] | None = None) -> dict:
    precondition = guard.live_snapshot(
        _runner(service=_service(environment)), _fetch
    )
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


def test_build_results_require_exact_provider_single_image_record():
    descriptor = _descriptor()
    build = _build_record(descriptor, "1" * 64)

    immutable = guard.immutable_image(build, "build-123")

    assert immutable == f"{guard.IMAGE_REPOSITORY}@sha256:" + "9" * 64


def test_successful_build_record_accepts_provider_single_image_record():
    descriptor = _descriptor()
    descriptor_sha = guard.sha256_bytes(guard.canonical(descriptor))
    build = _build_record(descriptor, descriptor_sha)

    result = guard.verify_build_record(
        descriptor,
        descriptor_sha,
        "build-123",
        run=_runner(build=build),
        require_success=True,
    )

    assert result["ok"] is True


def test_r2_provider_single_image_result_regression():
    build_id = "a12d5f93-cc3e-4af7-a532-3459b0839947"
    digest = "sha256:b91e2beecdd3c0183c1dd47e44c2e48547fa91f0d3cc7bd70d2ab4ab4bc73bc4"
    build = {
        "results": {
            "images": [
                {
                    "artifactRegistryPackage": (
                        "projects/sapphire-479610/locations/us/repositories/gcr.io/"
                        f"packages/sapphire-alpha-dashboard/versions/{digest}"
                    ),
                    "digest": digest,
                    "name": f"{guard.IMAGE_REPOSITORY}:{build_id}",
                    "pushTiming": {
                        "startTime": "2026-07-29T19:49:25.324038751Z",
                        "endTime": "2026-07-29T19:49:26.218924311Z",
                    },
                }
            ]
        }
    }

    assert guard.immutable_image(build, build_id) == (
        f"{guard.IMAGE_REPOSITORY}@{digest}"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "zero",
        "duplicate",
        "legacy_untagged_alias",
        "untagged",
        "wrong_tag",
        "invalid_digest",
        "package_mismatch",
        "missing_field",
        "extra_field",
        "missing_timing",
        "extra_timing",
        "empty_timing",
    ],
)
def test_build_results_reject_noncanonical_image_records(mutation):
    descriptor = _descriptor()
    build = _build_record(descriptor, "1" * 64)
    image = build["results"]["images"][0]
    if mutation == "zero":
        build["results"]["images"] = []
    elif mutation == "duplicate":
        build["results"]["images"].append(copy.deepcopy(image))
    elif mutation == "legacy_untagged_alias":
        alias = copy.deepcopy(image)
        alias["name"] = guard.IMAGE_REPOSITORY
        build["results"]["images"].insert(0, alias)
    elif mutation == "untagged":
        image["name"] = guard.IMAGE_REPOSITORY
    elif mutation == "wrong_tag":
        image["name"] = f"{guard.IMAGE_REPOSITORY}:other-build"
    elif mutation == "invalid_digest":
        image["digest"] = "sha256:not-a-digest"
    elif mutation == "package_mismatch":
        image["artifactRegistryPackage"] += "-other"
    elif mutation == "missing_field":
        image.pop("artifactRegistryPackage")
    elif mutation == "extra_field":
        image["media"] = "unexpected"
    elif mutation == "missing_timing":
        image["pushTiming"].pop("endTime")
    elif mutation == "extra_timing":
        image["pushTiming"]["duration"] = "1s"
    elif mutation == "empty_timing":
        image["pushTiming"]["endTime"] = ""

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


def test_provider_replacement_lets_cloud_run_allocate_a_new_revision_name():
    descriptor = _descriptor()
    service = _service()
    service["spec"]["template"]["metadata"] = {
        "annotations": {"run.googleapis.com/startup-cpu-boost": "true"},
        "generateName": "stale-provider-prefix-",
        "labels": {"run.googleapis.com/startupProbeType": "Default"},
        "name": READY,
    }
    image = f"{guard.IMAGE_REPOSITORY}@sha256:{'8' * 64}"

    replacement = guard.prepare_service_replacement(service, descriptor, image)

    template_metadata = replacement["spec"]["template"]["metadata"]
    assert "name" not in template_metadata
    assert "generateName" not in template_metadata
    assert template_metadata == {
        "annotations": {"run.googleapis.com/startup-cpu-boost": "true"},
        "labels": {"run.googleapis.com/startupProbeType": "Default"},
    }


@pytest.mark.parametrize(
    "missing",
    ["TELEMETRY_INGEST_SECRET", "MOSS_TELEMETRY_INGEST_SECRET"],
)
def test_provider_replacement_requires_durable_telemetry_secret_refs(missing):
    environment = [item for item in _environment() if item["name"] != missing]
    service = _service(environment)

    with pytest.raises(guard.ContractViolation, match="telemetry secret"):
        guard.prepare_service_replacement(
            service,
            _descriptor(environment=environment),
            f"{guard.IMAGE_REPOSITORY}@sha256:{'8' * 64}",
        )


def test_provider_http_error_preserves_bounded_noncontent_diagnostic_and_cause(
    monkeypatch,
):
    provider_token = "provider-token-that-must-not-escape"
    owner_phrase = "owner-phrase-that-must-not-escape"
    body = json.dumps(
        {
            "error": {
                "status": "RESOURCE_EXHAUSTED",
                "message": f"rate limited {owner_phrase}",
                "access_token": provider_token,
                "nested": {"cookie": SENTINEL},
            }
        }
    ).encode()
    provider_error = HTTPError(
        "https://provider.example.test",
        429,
        "rejected",
        {},
        BytesIO(body),
    )

    def reject(_request, timeout):
        assert timeout == 60
        raise provider_error

    monkeypatch.setattr(guard, "urlopen", reject)
    with pytest.raises(guard.ContractViolation) as raised:
        guard._replace_service_http(
            {"metadata": {"resourceVersion": "AAXY-example"}},
            run=lambda _argv: provider_token,
        )

    diagnostic = raised.value.diagnostic
    assert diagnostic == {
        "schema": "sapphire/provider-diagnostic/v1",
        "category": "provider_http_error",
        "http_status": 429,
        "capture_sha256": hashlib.sha256(body).hexdigest(),
        "capture_bytes": len(body),
        "capture_truncated": False,
    }
    assert raised.value.__cause__ is provider_error
    serialized = json.dumps(diagnostic, sort_keys=True).lower()
    assert provider_token not in serialized
    assert owner_phrase not in serialized
    assert SENTINEL not in serialized
    assert "response_body" not in diagnostic
    assert "message" not in diagnostic
    assert "provider_status" not in diagnostic


def test_provider_http_diagnostic_hashes_only_a_bounded_capture(monkeypatch):
    provider_token = "plain-token-that-must-not-escape"
    body = (
        "Authorization: Bearer " + provider_token + "\n"
        "Cookie: session=" + SENTINEL + "\n"
        "message=" + ("x" * 5000)
    ).encode()
    provider_error = HTTPError(
        "https://provider.example.test",
        503,
        "unavailable",
        {},
        BytesIO(body),
    )
    monkeypatch.setattr(
        guard,
        "urlopen",
        lambda _request, timeout: (_ for _ in ()).throw(provider_error),
    )

    with pytest.raises(guard.ContractViolation) as raised:
        guard._replace_service_http({}, run=lambda _argv: provider_token)

    diagnostic = raised.value.diagnostic
    serialized = json.dumps(diagnostic, sort_keys=True)
    assert diagnostic["http_status"] == 503
    assert diagnostic["capture_truncated"] is True
    assert diagnostic["capture_bytes"] == 4096
    assert diagnostic["capture_sha256"] == hashlib.sha256(body[:4096]).hexdigest()
    assert "response_body" not in diagnostic
    assert provider_token not in serialized
    assert SENTINEL not in serialized
    assert raised.value.__cause__ is provider_error


def test_provider_transport_error_is_distinguishable_without_exception_text(
    monkeypatch,
):
    provider_error = OSError(SENTINEL)
    monkeypatch.setattr(
        guard,
        "urlopen",
        lambda _request, timeout: (_ for _ in ()).throw(provider_error),
    )

    with pytest.raises(guard.ContractViolation) as raised:
        guard._replace_service_http({}, run=lambda _argv: "bounded-token")

    assert raised.value.diagnostic == {
        "schema": "sapphire/provider-diagnostic/v1",
        "category": "provider_transport_error",
        "reason": "transport_error",
    }
    assert SENTINEL not in json.dumps(raised.value.diagnostic)
    assert raised.value.__cause__ is provider_error


def test_trusted_launcher_retries_bounded_registry_eventual_consistency(monkeypatch):
    failures = [
        subprocess.CalledProcessError(1, ["gcloud"]),
        guard.ContractViolation("registry image mismatch"),
    ]
    attempts = []

    class EventuallyVisibleRegistry:
        ContractViolation = guard.ContractViolation

        @staticmethod
        def verify_registry_digest(build_id, image, run):
            assert callable(run)
            attempts.append((build_id, image))
            if failures:
                raise failures.pop(0)
            return {"ok": True}

    now = [100.0]
    sleeps = []
    monkeypatch.setattr(launcher.time, "monotonic", lambda: now[0])

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(launcher.time, "sleep", sleep)

    result = launcher._verify_registry_with_retry(
        EventuallyVisibleRegistry, "build-123", "immutable-image"
    )

    assert result == {"ok": True}
    assert attempts == [
        ("build-123", "immutable-image"),
        ("build-123", "immutable-image"),
        ("build-123", "immutable-image"),
    ]
    assert sleeps == [5, 5]


def test_trusted_launcher_registry_retry_expires_without_an_extra_attempt(
    monkeypatch,
):
    attempts = []

    class MissingRegistry:
        ContractViolation = guard.ContractViolation

        @staticmethod
        def verify_registry_digest(build_id, image, run):
            assert callable(run)
            attempts.append((build_id, image))
            now[0] = 160.0
            raise guard.ContractViolation("registry image mismatch")

    now = [100.0]
    sleeps = []
    monkeypatch.setattr(launcher.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(launcher.time, "sleep", sleeps.append)

    with pytest.raises(guard.ContractViolation, match="registry image mismatch"):
        launcher._verify_registry_with_retry(
            MissingRegistry, "build-123", "immutable-image"
        )

    assert attempts == [("build-123", "immutable-image")]
    assert sleeps == []


def test_trusted_launcher_caps_each_registry_process_to_remaining_time(monkeypatch):
    now = [100.0]
    timeouts = []
    sleeps = []

    class SlowRegistry:
        ContractViolation = guard.ContractViolation

        @staticmethod
        def _run(argv, *, timeout):
            timeouts.append(timeout)
            if len(timeouts) == 1:
                now[0] = 125.0
                raise subprocess.TimeoutExpired(argv, timeout)
            return "registry-visible"

        @staticmethod
        def verify_registry_digest(build_id, image, run):
            assert (build_id, image) == ("build-123", "immutable-image")
            run(["gcloud", "container", "images", "describe"])
            return {"ok": True}

    monkeypatch.setattr(launcher.time, "monotonic", lambda: now[0])

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(launcher.time, "sleep", sleep)

    result = launcher._verify_registry_with_retry(
        SlowRegistry, "build-123", "immutable-image"
    )

    assert result == {"ok": True}
    assert timeouts == [60.0, 30.0]
    assert sleeps == [5]


def test_trusted_launcher_suppresses_build_logs_and_accepts_one_uuid(
    monkeypatch, tmp_path
):
    build_id = "80a5477d-d79b-4278-813e-e038872a9111"
    calls = []

    def run(argv):
        calls.append(argv)
        return build_id + "\n"

    monkeypatch.setattr(launcher, "_run", run)

    assert launcher._submit_build(tmp_path / "cloudbuild.json") == build_id
    assert len(calls) == 1
    assert "--suppress-logs" in calls[0]
    assert "--format=value(id)" in calls[0]


@pytest.mark.parametrize(
    "output",
    [
        "",
        "REMOTE BUILD OUTPUT\n80a5477d-d79b-4278-813e-e038872a9111\n",
        "not-a-build-id\n",
    ],
)
def test_trusted_launcher_rejects_noncanonical_build_id_output(
    output, monkeypatch, tmp_path
):
    monkeypatch.setattr(launcher, "_run", lambda _argv: output)

    with pytest.raises(launcher.TrustFailure, match="build identity mismatch"):
        launcher._submit_build(tmp_path / "cloudbuild.json")


def test_trusted_launcher_carries_only_valid_structured_provider_diagnostic(
    monkeypatch, capsys
):
    failure = guard.ContractViolation("provider compare-and-swap rejected")
    failure.diagnostic = {
        "schema": "sapphire/provider-diagnostic/v1",
        "category": "provider_http_error",
        "http_status": 429,
        "capture_sha256": "a" * 64,
        "capture_bytes": 128,
        "capture_truncated": False,
    }
    monkeypatch.setattr(
        launcher,
        "release",
        lambda *_args: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "trusted_release.py",
            "run",
            "--descriptor",
            "descriptor.json",
            "--descriptor-sha256",
            "0" * 64,
        ],
    )

    assert launcher.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "schema": "sapphire/trusted-release-error/v1",
        "ok": False,
        "error": "release contract mismatch",
        "diagnostic": failure.diagnostic,
    }


def test_trusted_launcher_never_emits_unstructured_exception_text(monkeypatch, capsys):
    monkeypatch.setattr(
        launcher,
        "release",
        lambda *_args: (_ for _ in ()).throw(ValueError(SENTINEL)),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "trusted_release.py",
            "run",
            "--descriptor",
            "descriptor.json",
            "--descriptor-sha256",
            "0" * 64,
        ],
    )

    assert launcher.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "schema": "sapphire/trusted-release-error/v1",
        "ok": False,
        "error": "release contract mismatch",
    }
    assert SENTINEL not in json.dumps(result)


@pytest.mark.parametrize(
    "body",
    [
        b'{"message":"provider-secret-in-an-ordinary-value"}',
        b'{"message":"provider-secret-in-truncated-json',
        b"prefix Authorization: Bearer provider-secret-inline suffix",
        b"prefix owner phrase provider-secret-whitespace suffix",
        "prefix \u202e provider-secret-bidi suffix".encode(),
    ],
)
def test_actual_provider_failure_through_launcher_never_emits_body_text(
    body, monkeypatch, capsys
):
    provider_error = HTTPError(
        "https://provider.example.test",
        403,
        "forbidden",
        {},
        BytesIO(body),
    )
    monkeypatch.setattr(
        guard,
        "urlopen",
        lambda _request, timeout: (_ for _ in ()).throw(provider_error),
    )
    monkeypatch.setattr(
        launcher,
        "release",
        lambda *_args: guard._replace_service_http(
            {}, run=lambda _argv: "provider-token-not-in-body"
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "trusted_release.py",
            "run",
            "--descriptor",
            "descriptor.json",
            "--descriptor-sha256",
            "0" * 64,
        ],
    )

    assert launcher.main() == 1
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["diagnostic"]["http_status"] == 403
    assert result["diagnostic"]["capture_sha256"] == hashlib.sha256(body).hexdigest()
    assert b"provider-secret" not in output.encode()
    assert "response_body" not in output


def test_trusted_launcher_rejects_content_bearing_diagnostic(monkeypatch, capsys):
    failure = guard.ContractViolation("provider compare-and-swap rejected")
    failure.diagnostic = {
        "schema": "sapphire/provider-diagnostic/v1",
        "category": "provider_http_error",
        "http_status": 403,
        "response_body": '{"message":"provider-secret"}',
        "response_body_truncated": False,
    }
    monkeypatch.setattr(
        launcher,
        "release",
        lambda *_args: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "trusted_release.py",
            "run",
            "--descriptor",
            "descriptor.json",
            "--descriptor-sha256",
            "0" * 64,
        ],
    )

    assert launcher.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert "diagnostic" not in result
    assert "provider-secret" not in json.dumps(result)


class _ProviderResponse:
    def __init__(self, payload):
        self.payload = payload
        self.read_amount = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, amount=None):
        self.read_amount = amount
        return self.payload if amount is None else self.payload[:amount]


def test_provider_success_response_is_bounded_before_json_decode(monkeypatch):
    payload = b'{"payload":"' + (b"x" * (1024 * 1024)) + b'"}'
    response = _ProviderResponse(payload)
    monkeypatch.setattr(guard, "urlopen", lambda _request, timeout: response)

    with pytest.raises(guard.ContractViolation) as raised:
        guard._replace_service_http({}, run=lambda _argv: "bounded-token")

    assert raised.value.diagnostic == {
        "schema": "sapphire/provider-diagnostic/v1",
        "category": "provider_response_invalid",
        "reason": "response_too_large",
    }
    assert response.read_amount == 1024 * 1024 + 1


@pytest.mark.parametrize("payload", [b"[]", b'"scalar"', b"null"])
def test_provider_valid_json_non_object_has_structured_diagnostic(
    payload, monkeypatch
):
    response = _ProviderResponse(payload)
    monkeypatch.setattr(guard, "urlopen", lambda _request, timeout: response)

    with pytest.raises(guard.ContractViolation) as raised:
        guard._replace_service_http({}, run=lambda _argv: "bounded-token")

    assert raised.value.diagnostic == {
        "schema": "sapphire/provider-diagnostic/v1",
        "category": "provider_response_invalid",
        "reason": "non_object",
    }


def test_provider_invalid_json_has_structured_diagnostic_and_cause(monkeypatch):
    response = _ProviderResponse(b"{not-json")
    monkeypatch.setattr(guard, "urlopen", lambda _request, timeout: response)

    with pytest.raises(guard.ContractViolation) as raised:
        guard._replace_service_http({}, run=lambda _argv: "bounded-token")

    assert raised.value.diagnostic == {
        "schema": "sapphire/provider-diagnostic/v1",
        "category": "provider_response_invalid",
        "reason": "invalid_json",
    }
    assert isinstance(raised.value.__cause__, json.JSONDecodeError)


@pytest.mark.parametrize(
    "payload, exception_type",
    [
        (b'{"x":' + (b"9" * 5000) + b"}", ValueError),
        ((b"[" * 10000) + (b"]" * 10000), RecursionError),
    ],
)
def test_provider_json_parser_limits_remain_structured(
    payload, exception_type, monkeypatch
):
    response = _ProviderResponse(payload)
    monkeypatch.setattr(guard, "urlopen", lambda _request, timeout: response)

    with pytest.raises(guard.ContractViolation) as raised:
        guard._replace_service_http({}, run=lambda _argv: "bounded-token")

    assert raised.value.diagnostic == {
        "schema": "sapphire/provider-diagnostic/v1",
        "category": "provider_response_invalid",
        "reason": "invalid_json",
    }
    assert isinstance(raised.value.__cause__, exception_type)


@pytest.mark.parametrize(
    "capture_sha256,capture_bytes,capture_truncated",
    [
        ("a" * 64, 0, False),
        (hashlib.sha256(b"").hexdigest(), 0, True),
        ("a" * 64, 1, True),
        ("a" * 64, 4095, True),
    ],
)
def test_trusted_launcher_rejects_impossible_capture_semantics(
    capture_sha256,
    capture_bytes,
    capture_truncated,
    monkeypatch,
    capsys,
):
    failure = guard.ContractViolation("provider compare-and-swap rejected")
    failure.diagnostic = {
        "schema": "sapphire/provider-diagnostic/v1",
        "category": "provider_http_error",
        "http_status": 403,
        "capture_sha256": capture_sha256,
        "capture_bytes": capture_bytes,
        "capture_truncated": capture_truncated,
    }
    monkeypatch.setattr(
        launcher,
        "release",
        lambda *_args: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "trusted_release.py",
            "run",
            "--descriptor",
            "descriptor.json",
            "--descriptor-sha256",
            "0" * 64,
        ],
    )

    assert launcher.main() == 1
    assert "diagnostic" not in json.loads(capsys.readouterr().out)


def test_transport_exception_class_name_never_reaches_launcher(monkeypatch, capsys):
    secret_type = type("ProviderSecretCredential", (OSError,), {})
    provider_error = secret_type("opaque")
    monkeypatch.setattr(
        guard,
        "urlopen",
        lambda _request, timeout: (_ for _ in ()).throw(provider_error),
    )
    monkeypatch.setattr(
        launcher,
        "release",
        lambda *_args: guard._replace_service_http(
            {}, run=lambda _argv: "bounded-token"
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "trusted_release.py",
            "run",
            "--descriptor",
            "descriptor.json",
            "--descriptor-sha256",
            "0" * 64,
        ],
    )

    assert launcher.main() == 1
    output = capsys.readouterr().out
    assert "ProviderSecretCredential" not in output
    assert json.loads(output)["diagnostic"] == {
        "schema": "sapphire/provider-diagnostic/v1",
        "category": "provider_transport_error",
        "reason": "transport_error",
    }


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


@pytest.mark.parametrize(
    "response,reason",
    [
        ({}, "metadata_invalid"),
        ({"metadata": []}, "metadata_invalid"),
        (
            {"metadata": {"name": guard.SERVICE}},
            "resource_version_invalid",
        ),
        (
            {
                "metadata": {
                    "name": guard.SERVICE,
                    "resourceVersion": "AAXY-example",
                }
            },
            "resource_version_unchanged",
        ),
        (
            {
                "metadata": {
                    "name": "other-service",
                    "resourceVersion": "new-version",
                }
            },
            "service_name_mismatch",
        ),
    ],
)
def test_provider_cas_response_failure_has_bounded_noncontent_diagnostic(
    response, reason, monkeypatch
):
    descriptor = _descriptor()
    service = _service()
    image = f"{guard.IMAGE_REPOSITORY}@sha256:{'8' * 64}"
    monkeypatch.setattr(
        guard,
        "verify_predeploy_cas",
        lambda *_args, **_kwargs: {"ok": True},
    )

    with pytest.raises(guard.ContractViolation) as raised:
        guard.deploy_with_provider_cas(
            descriptor,
            image,
            run=_runner(service=service),
            fetch=_fetch,
            replace=lambda _replacement: response,
        )

    assert raised.value.diagnostic == {
        "schema": "sapphire/provider-diagnostic/v1",
        "category": "provider_cas_response_rejected",
        "reason": reason,
    }
    assert SENTINEL not in json.dumps(raised.value.diagnostic)


def test_trusted_launcher_carries_bounded_provider_cas_response_diagnostic(
    monkeypatch, capsys
):
    failure = guard.ProviderRequestFailure(
        {
            "schema": "sapphire/provider-diagnostic/v1",
            "category": "provider_cas_response_rejected",
            "reason": "resource_version_unchanged",
        }
    )
    monkeypatch.setattr(
        launcher,
        "release",
        lambda *_args: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "trusted_release.py",
            "run",
            "--descriptor",
            "descriptor.json",
            "--descriptor-sha256",
            "0" * 64,
        ],
    )

    assert launcher.main() == 1
    assert json.loads(capsys.readouterr().out)["diagnostic"] == failure.diagnostic


@pytest.mark.parametrize("reason", [SENTINEL, "", None])
def test_trusted_launcher_rejects_unknown_provider_cas_response_reason(
    reason, monkeypatch, capsys
):
    failure = guard.ProviderRequestFailure(
        {
            "schema": "sapphire/provider-diagnostic/v1",
            "category": "provider_cas_response_rejected",
            "reason": reason,
        }
    )
    monkeypatch.setattr(
        launcher,
        "release",
        lambda *_args: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "trusted_release.py",
            "run",
            "--descriptor",
            "descriptor.json",
            "--descriptor-sha256",
            "0" * 64,
        ],
    )

    assert launcher.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert "diagnostic" not in result
    assert SENTINEL not in json.dumps(result)


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


def test_registry_readback_queries_the_exact_immutable_digest():
    immutable = f"{guard.IMAGE_REPOSITORY}@sha256:{'8' * 64}"

    def runner(argv):
        image_arguments = [
            value for value in argv if value.startswith(guard.IMAGE_REPOSITORY)
        ]
        assert len(image_arguments) == 1
        assert image_arguments[0].startswith(f"{guard.IMAGE_REPOSITORY}@sha256:")
        assert f"{guard.IMAGE_REPOSITORY}:build-123" not in argv
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

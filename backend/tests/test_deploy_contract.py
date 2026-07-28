"""Hostile goldens for the content-addressed release guard."""

from __future__ import annotations

import base64
import copy
from io import BytesIO
import json
from urllib.error import HTTPError
import zlib

import pytest

from scripts import deploy_contract as guard


SENTINEL = "never-emit-runtime-canary"
READY = "sapphire-alpha-dashboard-00073-kv2"
CREATED = "sapphire-alpha-dashboard-00074-p42"
READY_DIGEST = "sha256:" + "a" * 64
CREATED_DIGEST = "sha256:" + "b" * 64
SOURCE_SHA = "c" * 40
ARCHIVE_SHA = "d" * 64
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
        "metadata": {"generation": 82},
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
            "archive_sha256": ARCHIVE_SHA,
            "manifest_sha256": MANIFEST_SHA,
            "file_count": 200,
            "bucket": guard.STAGING_BUCKET,
            "object": f"source/sapphire/{ARCHIVE_SHA}.tar.gz",
            "generation": 123456,
            "bucket_configuration_sha256": "f" * 64,
        },
        "precondition": precondition,
        "postcondition": {
            "iam_sha256": precondition["iam_sha256"],
            "service_account": precondition["service_account"],
            "environment": precondition["environment"],
            "service_url": precondition["service_url"],
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
    exact_key = f"gs://{source['bucket']}/{source['object']}"
    archive_b64 = base64.b64encode(bytes.fromhex(ARCHIVE_SHA)).decode()
    return {
        "id": "build-123",
        "status": "SUCCESS",
        "source": {"storageSource": copy.deepcopy(storage)},
        "sourceProvenance": {
            "resolvedStorageSource": copy.deepcopy(storage),
            "fileHashes": {
                exact_key: {
                    "fileHash": [{"type": "SHA256", "value": archive_b64}]
                }
            },
        },
        "substitutions": {
            "_ACTION_DESCRIPTOR_ZLIB_B64": base64.b64encode(
                zlib.compress(guard.canonical(descriptor), level=9)
            ).decode(),
            "_ACTION_DESCRIPTOR_SHA256": descriptor_sha,
            "_BUILD_SHA": SOURCE_SHA,
            "_SOURCE_ARCHIVE_SHA256": ARCHIVE_SHA,
            "_SOURCE_GENERATION": str(source["generation"]),
            "_SOURCE_MANIFEST_SHA256": MANIFEST_SHA,
            "_SOURCE_OBJECT": source["object"],
        },
        "results": {
            "images": [
                {
                    "name": f"{guard.IMAGE_REPOSITORY}:build-123",
                    "digest": "sha256:" + "9" * 64,
                }
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
    monkeypatch.setattr(guard, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(error))
    assert guard.fetch_http("https://service.example.test/api/build") == (
        404,
        '{"detail":"not found"}',
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda service, policy: service["metadata"].update(generation=83),
        lambda service, policy: service["status"].update(observedGeneration=83),
        lambda service, policy: service["status"].update(latestReadyRevisionName=CREATED),
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
    ["missing_submitted_generation", "wrong_key", "extra_hash", "resolved_generation"],
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
    else:
        provenance["resolvedStorageSource"]["generation"] = "999"
    assert guard.source_provenance_exact(build, descriptor) is False


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
    }
    monkeypatch.setattr(guard, "verify_build_record", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(guard, "live_snapshot", lambda *_args, **_kwargs: current)
    result = guard.verify_postdeploy(
        descriptor,
        descriptor_sha,
        "build-123",
        run=_runner(build=build),
        fetch=_fetch,
    )
    assert result["ok"] is True

    current["generation"] = 84
    with pytest.raises(guard.ContractViolation, match="postdeploy state mismatch"):
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

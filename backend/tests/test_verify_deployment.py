import json
from pathlib import Path
from io import BytesIO
from urllib.error import HTTPError

from scripts import verify_deployment
from scripts.verify_deployment import PAGE_CONTRACTS, verify


ROOT = Path(__file__).resolve().parents[2]


def _build_payload(sha: str) -> dict:
    surface = {
        "entrypoint_url": "/",
        "entrypoint_sha256": "a" * 64,
        "asset_count": 3,
        "manifest_sha256": "b" * 64,
    }
    return {
        "schema": 1,
        "source_sha": sha,
        "build_id": "build-123",
        "runtime_revision": "sapphire-alpha-dashboard-00042-abc",
        "surfaces": {"operator": surface, "public": surface},
        "complete": True,
    }


def test_verify_deployment_binds_revision_and_three_public_markers():
    sha = "c" * 40
    expected = _build_payload(sha)
    responses = {
        "/api/build": json.dumps(_build_payload(sha)),
        "/": '<section id="public-title">',
        "/dashboard": '<div id="root"></div>',
        "/research/calibration-2026-07-27/": (
            "<title>Learning loop — wins, losses, calibration — Sapphire Alpha</title>"
        ),
    }

    def fetch(url: str) -> tuple[int, str]:
        path = url.removeprefix("https://example.test")
        return 200, responses[path]

    result = verify("https://example.test/", expected, fetch)

    assert result["ok"] is True
    assert result["runtime_revision"] == "sapphire-alpha-dashboard-00042-abc"
    assert all(result["checks"].values())


def test_verify_deployment_fails_on_wrong_source_or_missing_marker():
    expected = "d" * 40
    expected_identity = _build_payload(expected)

    def fetch(url: str) -> tuple[int, str]:
        if url.endswith("/api/build"):
            return 200, json.dumps(_build_payload("e" * 40))
        return 200, "wrong page"

    result = verify("https://example.test", expected_identity, fetch)

    assert result["ok"] is False
    assert result["checks"]["build_identity_exact"] is False
    assert result["checks"]["public_home"] is False
    assert "deployed_sha" not in result
    assert "build_id" not in result
    assert "runtime_revision" not in result


def test_verify_deployment_rejects_arbitrary_well_formed_surface_hashes():
    expected = _build_payload("d" * 40)
    observed = json.loads(json.dumps(expected))
    observed["surfaces"]["public"]["manifest_sha256"] = "f" * 64

    def fetch(url: str) -> tuple[int, str]:
        if url.endswith("/api/build"):
            return 200, json.dumps(observed)
        if url.endswith("/dashboard"):
            return 200, '<div id="root"></div>'
        if url.endswith("/research/calibration-2026-07-27/"):
            return 200, "<title>Learning loop — wins, losses, calibration"
        return 200, '<section id="public-title">'

    result = verify("https://example.test", expected, fetch)

    assert result["ok"] is False
    assert result["checks"]["build_identity_exact"] is False


def test_fetch_turns_real_http_error_into_expected_status(monkeypatch):
    error = HTTPError(
        "https://example.test/api/build",
        404,
        "not found",
        {},
        BytesIO(b'{"detail":"not found"}'),
    )
    monkeypatch.setattr(
        verify_deployment,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    assert verify_deployment._fetch("https://example.test/api/build") == (
        404,
        '{"detail":"not found"}',
    )


def test_readback_markers_are_pinned_to_source_contracts():
    public_source = (ROOT / "web/src/components/MissionControl.tsx").read_text()
    operator_source = (ROOT / "frontend/index.html").read_text()
    calibration_source = (
        ROOT / "web/content/research/calibration-2026-07-27.md"
    ).read_text()

    assert "public-title" in public_source
    assert PAGE_CONTRACTS["operator_home"][1] in operator_source
    assert "Learning loop — wins, losses, calibration" in calibration_source

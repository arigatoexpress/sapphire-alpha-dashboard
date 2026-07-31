"""Fleet snapshot endpoint (/api/fleet).

Reads a sanitized fleet.json produced by `fleet-lease export --sanitized`
(FLEET_SNAPSHOT_PATH env, default ./data/fleet.json) and serves it with a
staleness field. Auth required; in PUBLIC_READ_ONLY anonymous mode only
counts are returned. The backend never trusts the file: fields are
whitelisted so a poisoned snapshot cannot leak paths or extra keys.
"""

import hashlib
import hmac
import json
import os
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_USERNAME"] = "testuser"
os.environ["AUTH_PASSWORD"] = "testpass-strong-99"

import main
from main import app

client = TestClient(app)

AUTH = ("testuser", "testpass-strong-99")
INGEST_SECRET = "fleet-telemetry-test-secret-that-is-long-enough"


def _snapshot(generated_at: str | None = None) -> dict:
    return {
        "generated_at": generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "leases": [
            {
                "agent": "claude-ops-pane",
                "repo": "fleet-lease",
                "purpose": "fleet ops pane build",
                "expires_at": "2026-07-17T01:23:29+00:00",
            }
        ],
        "gates": [
            {"id": 7, "title": "prod cutover", "age_hours": 3.2, "status": "open"},
        ],
        "counts": {"leases": 1, "gates_open": 1},
    }


def _signed_headers(raw: bytes, *, nonce: str = "fleetnonce0001") -> dict[str, str]:
    timestamp = str(int(time.time()))
    message = timestamp.encode() + b"." + nonce.encode() + b"." + raw
    signature = hmac.new(
        INGEST_SECRET.encode(), message, hashlib.sha256
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Sapphire-Timestamp": timestamp,
        "X-Sapphire-Nonce": nonce,
        "X-Sapphire-Signature": signature,
    }


@pytest.fixture
def fleet_file(tmp_path, monkeypatch):
    main.fleet_telemetry_store.reset()
    path = tmp_path / "fleet.json"
    monkeypatch.setenv("FLEET_SNAPSHOT_PATH", str(path))
    yield path
    main.fleet_telemetry_store.reset()


# --- auth ---------------------------------------------------------------------


def test_fleet_get_is_anonymous_but_sanitized(monkeypatch, fleet_file):
    """Reads are public now; the sanitizer, not the auth gate, is the protection."""
    monkeypatch.delenv("PUBLIC_READ_ONLY", raising=False)
    fleet_file.write_text(json.dumps(_snapshot()), encoding="utf-8")
    r = client.get("/api/fleet")
    assert r.status_code == 200
    assert r.json()["public_view"] is True


def test_fleet_non_get_still_requires_auth(fleet_file):
    r = client.post("/api/fleet")
    assert r.status_code in (401, 405)
    assert r.status_code != 200


def test_fleet_wrong_creds_rejected_even_in_public_mode(monkeypatch, fleet_file):
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    r = client.get("/api/fleet", auth=("not-the-user", "testpass-strong-99"))
    assert r.status_code == 401


# --- missing / invalid snapshot -------------------------------------------------


def test_fleet_missing_file_returns_empty_shape(fleet_file):
    r = client.get("/api/fleet", auth=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["leases"] == []
    assert data["gates"] == []
    assert data["counts"] == {"leases": None, "gates_open": None}
    assert data["generated_at"] is None
    assert data["snapshot_age_s"] is None


def test_fleet_invalid_json_returns_empty_shape(fleet_file):
    fleet_file.write_text("{not json", encoding="utf-8")
    r = client.get("/api/fleet", auth=AUTH)
    assert r.status_code == 200
    assert r.json()["counts"] == {"leases": None, "gates_open": None}


def test_signed_fleet_ingest_persists_without_a_local_snapshot(monkeypatch, fleet_file):
    monkeypatch.setenv("TELEMETRY_INGEST_SECRET", INGEST_SECRET)
    main.fleet_telemetry_store.reset()
    payload = dict(_snapshot(), version=1, sequence=time.time_ns())
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()

    accepted = client.post(
        "/api/v1/fleet/telemetry",
        content=raw,
        headers=_signed_headers(raw),
    )
    assert accepted.status_code == 202
    assert accepted.json() == {
        "accepted": True,
        "sequence": payload["sequence"],
    }

    public = client.get("/api/fleet")
    assert public.status_code == 200
    assert public.json()["leases"] == 1
    assert public.json()["gates_open"] == 1
    assert public.json()["snapshot_age_s"] is not None


def test_fleet_ingest_rejects_invalid_signature_and_replay(monkeypatch, fleet_file):
    monkeypatch.setenv("TELEMETRY_INGEST_SECRET", INGEST_SECRET)
    main.fleet_telemetry_store.reset()
    payload = dict(_snapshot(), version=1, sequence=time.time_ns())
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    headers = _signed_headers(raw, nonce="fleetnonce0002")

    invalid = dict(headers, **{"X-Sapphire-Signature": "0" * 64})
    assert client.post(
        "/api/v1/fleet/telemetry", content=raw, headers=invalid
    ).status_code == 401

    assert client.post(
        "/api/v1/fleet/telemetry", content=raw, headers=headers
    ).status_code == 202
    assert client.post(
        "/api/v1/fleet/telemetry", content=raw, headers=headers
    ).status_code == 409


def test_fleet_ingest_rejects_extra_fields_and_false_counts(monkeypatch, fleet_file):
    monkeypatch.setenv("TELEMETRY_INGEST_SECRET", INGEST_SECRET)
    main.fleet_telemetry_store.reset()
    payload = dict(
        _snapshot(),
        version=1,
        sequence=time.time_ns(),
        internal_path="/private/fleet-lease.db",
    )
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    rejected = client.post(
        "/api/v1/fleet/telemetry",
        content=raw,
        headers=_signed_headers(raw, nonce="fleetnonce0003"),
    )
    assert rejected.status_code == 422

    payload.pop("internal_path")
    payload["counts"] = {"leases": 99, "gates_open": 1}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    rejected = client.post(
        "/api/v1/fleet/telemetry",
        content=raw,
        headers=_signed_headers(raw, nonce="fleetnonce0004"),
    )
    assert rejected.status_code == 422


# --- authed happy path -----------------------------------------------------------


def test_fleet_authed_full_payload_with_staleness(fleet_file):
    fleet_file.write_text(json.dumps(_snapshot()), encoding="utf-8")
    r = client.get("/api/fleet", auth=AUTH)
    assert r.status_code == 200
    data = r.json()
    (lease,) = data["leases"]
    assert lease == {
        "agent": "claude-ops-pane",
        "repo": "fleet-lease",
        "purpose": "fleet ops pane build",
        "expires_at": "2026-07-17T01:23:29+00:00",
    }
    (gate,) = data["gates"]
    assert gate == {"id": 7, "title": "prod cutover", "age_hours": 3.2, "status": "open"}
    assert data["counts"] == {"leases": 1, "gates_open": 1}
    assert isinstance(data["snapshot_age_s"], (int, float))
    assert 0 <= data["snapshot_age_s"] < 120


def test_fleet_staleness_reflects_old_snapshot(fleet_file):
    old = (datetime.now(UTC) - timedelta(hours=1)).isoformat(timespec="seconds")
    fleet_file.write_text(json.dumps(_snapshot(generated_at=old)), encoding="utf-8")
    r = client.get("/api/fleet", auth=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["snapshot_age_s"] >= 3500
    assert data["leases"] == []
    assert data["gates"] == []
    assert data["counts"] == {"leases": None, "gates_open": None}


# --- defense in depth: never trust the file --------------------------------------


def test_fleet_poisoned_snapshot_is_whitelisted(fleet_file):
    snap = _snapshot()
    snap["leases"][0]["path"] = "/Users/aribs/Code/secret-repo"
    snap["leases"][0]["token"] = "sk-secret"
    snap["gates"][0]["action_hint"] = "gcloud run deploy --project=x"
    snap["internal"] = {"db": "/Users/aribs/ops-state/fleet-lease.db"}
    fleet_file.write_text(json.dumps(snap), encoding="utf-8")
    r = client.get("/api/fleet", auth=AUTH)
    assert r.status_code == 200
    body = json.dumps(r.json())
    assert "/Users/" not in body
    assert "sk-secret" not in body
    assert "action_hint" not in body
    assert "internal" not in body


# --- anonymous public read-only: counts only --------------------------------------


def test_fleet_anonymous_counts_only(monkeypatch, fleet_file):
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    fleet_file.write_text(json.dumps(_snapshot()), encoding="utf-8")
    r = client.get("/api/fleet")
    assert r.status_code == 200
    data = r.json()
    assert data["public_view"] is True
    assert data["leases"] == 1
    assert data["gates_open"] == 1
    assert isinstance(data["snapshot_age_s"], (int, float))
    assert set(data) == {"public_view", "leases", "gates_open", "snapshot_age_s"}
    assert "prod cutover" not in json.dumps(data)
    assert "claude-ops-pane" not in json.dumps(data)


def test_fleet_anonymous_payload_has_no_path_like_strings(monkeypatch, fleet_file):
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    snap = _snapshot()
    snap["leases"][0]["repo"] = "/Users/aribs/Code/leaky"  # poisoned snapshot
    fleet_file.write_text(json.dumps(snap), encoding="utf-8")
    r = client.get("/api/fleet")
    assert r.status_code == 200
    body = json.dumps(r.json())
    assert "/Users/" not in body
    assert "aribs" not in body
    assert not any("/" in str(v) for v in r.json().values())


def test_fleet_anonymous_missing_file(monkeypatch, fleet_file):
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    r = client.get("/api/fleet")
    assert r.status_code == 200
    assert r.json() == {
        "public_view": True,
        "leases": None,
        "gates_open": None,
        "snapshot_age_s": None,
    }


def test_fleet_authed_user_gets_full_payload_in_public_mode(monkeypatch, fleet_file):
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    fleet_file.write_text(json.dumps(_snapshot()), encoding="utf-8")
    r = client.get("/api/fleet", auth=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["leases"][0]["repo"] == "fleet-lease"
    assert "public_view" not in data


# --- security headers + rate limiting ---------------------------------------------


def test_fleet_security_headers_present(fleet_file):
    r = client.get("/api/fleet", auth=AUTH)
    for name in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
    ):
        assert name in r.headers


def test_fleet_is_rate_limited_like_other_api_routes(fleet_file):
    """The route must carry the shared _api_rate_limit limiter."""
    main.limiter.reset()
    try:
        route = next(r for r in app.routes if getattr(r, "path", "") == "/api/fleet")
        assert getattr(route.endpoint, "__wrapped__", None) is not None  # limiter wraps it
        statuses = [client.get("/api/fleet", auth=AUTH).status_code for _ in range(61)]
        assert statuses[-1] == 429
    finally:
        main.limiter.reset()

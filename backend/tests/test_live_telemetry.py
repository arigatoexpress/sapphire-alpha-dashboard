"""Golden contract for signed, public-safe live telemetry."""

from __future__ import annotations

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

import live_telemetry
import main
from main import app
from live_telemetry import LiveTelemetryStore, MemoryTelemetryPersistence


client = TestClient(app)
AUTH = ("testuser", "testpass-strong-99")
SECRET = "telemetry-test-secret-that-is-long-enough"


def _sample(*, observed_at: str | None = None, sequence: int = 42) -> dict:
    now = observed_at or datetime.now(UTC).isoformat()
    return {
        "version": 1,
        "observed_at": now,
        "sequence": sequence,
        "summary": {
            "state": "observing",
            "active_agents": 4,
            "events_per_min": 37.2,
            "verified_today": 12,
            "attention": 1,
        },
        "nodes": [
            {
                "id": "edge",
                "zone": "edge",
                "label": "Public edge",
                "status": "healthy",
                "load": "low",
                "activity_rate": 8.0,
                "freshness_s": 2.1,
            },
            {
                "id": "compute",
                "zone": "compute",
                "label": "GPU compute",
                "status": "healthy",
                "load": "medium",
                "activity_rate": 18.0,
                "freshness_s": 1.2,
            },
        ],
        "links": [
            {
                "source": "edge",
                "target": "compute",
                "status": "healthy",
                "latency_ms": 7.4,
                "event_rate": 18.0,
                "signal_class": "network",
            }
        ],
        "agents": [
            {
                "id": "research-scout",
                "role": "Research scout",
                "state": "working",
                "activity": "Comparing market signals",
                "verification": "pending",
                "provider_class": "local GPU",
                "updated_at": now,
            }
        ],
        "markets": {
            "network": "Robinhood Chain",
            "status": "current",
            "feed_age_s": 4.2,
            "events_per_min": 19.0,
            "paper_strategies": 7,
            "decision_gate": "telegram",
            "execution": "off",
        },
        "desk": {
            "version": 1,
            "updated_at": now,
            "posture": "capital_preservation",
            "leader": "none",
            "validation": {"oos_pass": 0, "oos_total": 7, "conflicts": 1},
            "decisions": {"pending": 2},
            "execution": "halted",
            "feeds": {"fresh": 7, "total": 7},
        },
        "events": [
            {
                "id": "evt-42",
                "observed_at": now,
                "event_class": "agent",
                "source": "intelligence",
                "target": "archive",
                "label": "Research result verified",
                "status": "verified",
            }
        ],
    }


def _signed(payload: dict, *, nonce: str = "nonce-0000000001", timestamp: int | None = None):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    ts = str(timestamp or int(time.time()))
    message = ts.encode() + b"." + nonce.encode() + b"." + raw
    signature = hmac.new(SECRET.encode(), message, hashlib.sha256).hexdigest()
    return raw, {
        "Content-Type": "application/json",
        "X-Sapphire-Timestamp": ts,
        "X-Sapphire-Nonce": nonce,
        "X-Sapphire-Signature": signature,
    }


@pytest.fixture(autouse=True)
def telemetry_state(monkeypatch):
    monkeypatch.setenv("TELEMETRY_INGEST_SECRET", SECRET)
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    monkeypatch.setenv("PUBLIC_TELEMETRY_DELAY_SECONDS", "0")
    main._reset_live_telemetry_for_tests()
    yield
    main._reset_live_telemetry_for_tests()


def test_no_snapshot_is_honest_and_never_synthetic():
    public = client.get("/api/v1/live").json()
    assert public["status"] == "offline"
    assert public["events"] == []
    assert public["agents"] == []
    assert public["summary"]["state"] == "not observed"
    assert "RICH" not in json.dumps(public)


def test_signed_ingest_and_operator_projection():
    raw, headers = _signed(_sample())
    accepted = client.post("/api/v1/telemetry", content=raw, headers=headers)
    assert accepted.status_code == 202
    assert accepted.json()["accepted"] is True

    live = client.get("/api/v1/live", auth=AUTH).json()
    assert live["status"] == "live"
    assert live["sequence"] == 42
    assert live["links"][0]["latency_ms"] == 7.4
    assert live["agents"][0]["activity"] == "Comparing market signals"
    assert live["desk"]["leader"] == "none"
    assert live["desk"]["validation"] == {
        "oos_pass": 0,
        "oos_total": 7,
        "conflicts": 1,
    }


def test_legacy_producer_without_desk_gets_honest_unknown_projection():
    payload = _sample()
    payload.pop("desk")
    normalized = live_telemetry.validate_snapshot(payload)
    assert normalized["desk"]["posture"] == "unknown"
    assert normalized["desk"]["decisions"]["pending"] is None


def test_desk_projection_rejects_private_or_unbounded_detail():
    payload = _sample()
    payload["desk"]["source"] = "named analyst"
    raw, headers = _signed(payload, nonce="nonce-private-desk-01")
    response = client.post("/api/v1/telemetry", content=raw, headers=headers)
    assert response.status_code == 422


def test_bad_signature_and_stale_timestamp_fail_closed():
    raw, headers = _signed(_sample())
    headers["X-Sapphire-Signature"] = "0" * 64
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 401

    raw, headers = _signed(_sample(), nonce="nonce-0000000002", timestamp=int(time.time()) - 301)
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 401


def test_nonce_replay_is_rejected():
    raw, headers = _signed(_sample(), nonce="nonce-replay-0001")
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 202
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 409


def test_shared_persistence_enforces_sequence_across_instances():
    persistence = MemoryTelemetryPersistence()
    first = LiveTelemetryStore(persistence)
    second = LiveTelemetryStore(persistence)
    raw, headers = _signed(_sample(sequence=80), nonce="nonce-instance-001")
    first.accept(body=raw, headers={key.lower(): value for key, value in headers.items()}, secret=SECRET, parsed_json=json.loads(raw))

    older, older_headers = _signed(_sample(sequence=79), nonce="nonce-instance-002")
    with pytest.raises(main.TelemetryValidationError):
        second.accept(body=older, headers={key.lower(): value for key, value in older_headers.items()}, secret=SECRET, parsed_json=json.loads(older))
    assert second.get(public=False)["sequence"] == 80


def test_oversized_body_is_rejected():
    payload = _sample()
    payload["events"][0]["label"] = "x" * 70_000
    raw, headers = _signed(payload, nonce="nonce-oversize-01")
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 413


@pytest.mark.parametrize(
    "poison",
    [
        {"hostname": "desktop-hfck6u9-2"},
        {"endpoint": "http://192.0.2.1:11434"},
        {"path": "/Users/aribs/ops-state"},
        {"api_token": "secret"},
    ],
)
def test_attack_useful_or_secret_fields_are_rejected(poison):
    payload = _sample()
    payload["nodes"][0].update(poison)
    raw, headers = _signed(payload, nonce=f"nonce-poison-{next(iter(poison))}")
    response = client.post("/api/v1/telemetry", content=raw, headers=headers)
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        (("agents", 0, "role"), "owner@example.com"),
        (("agents", 0, "activity"), "Call 303-555-0199"),
        (("events", 0, "label"), "Ask @private_handle"),
        (("events", 0, "label"), "Reference 123-45-6789"),
    ],
)
def test_public_prose_rejects_common_personal_identifiers(field_path, value):
    """Role/activity/event prose is public and producer-controlled. Bounded
    length alone is not a privacy boundary, so common direct identifiers fail
    closed before storage."""
    payload = _sample()
    collection, index, field = field_path
    payload[collection][index][field] = value
    raw, headers = _signed(payload, nonce=f"nonce-pii-{field}-{index}-{len(value)}")
    response = client.post("/api/v1/telemetry", content=raw, headers=headers)
    assert response.status_code == 422
    assert "personal identifier" in response.json()["detail"]


def test_nullable_activity_summary_and_market_measurements_survive_ingest():
    payload = _sample()
    payload["summary"].update(
        {
            "active_agents": None,
            "events_per_min": None,
            "verified_today": None,
            "attention": None,
        }
    )
    payload["nodes"][0]["activity_rate"] = None
    payload["links"][0]["event_rate"] = None
    payload["markets"].update(
        {
            "feed_age_s": None,
            "events_per_min": None,
            "paper_strategies": None,
        }
    )
    raw, headers = _signed(payload, nonce="nonce-nullable-001")
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 202
    live = client.get("/api/v1/live").json()
    assert live["summary"]["active_agents"] is None
    assert live["summary"]["events_per_min"] is None
    assert live["summary"]["verified_today"] is None
    assert live["summary"]["attention"] is None
    assert live["nodes"][0]["activity_rate"] is None
    assert live["links"][0]["event_rate"] is None
    assert live["markets"]["feed_age_s"] is None
    assert live["markets"]["events_per_min"] is None
    assert live["markets"]["paper_strategies"] is None


def test_anonymous_view_is_unredacted_but_still_leaks_no_internal_identifiers():
    """The redaction tier is gone; the ingest contract is what keeps this safe.

    This used to assert the public projection bucketed timings into adjectives.
    Bucketing is deleted (Ari, 2026-07-25) — anonymous readers get the real
    numbers. What survives, and is the part that was ever load-bearing, is that
    no hostname, path, address or secret can be in the payload at all, because
    validate_snapshot rejects them at ingest rather than scrubbing them on read.
    """
    raw, headers = _signed(_sample(), nonce="nonce-public-0001")
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 202

    public = client.get("/api/v1/live").json()
    body = json.dumps(public)
    assert public["links"][0]["latency_ms"] == 7.4
    assert public["links"][0]["event_rate"] == 18.0
    assert public["agents"][0]["role"] == "Research scout"
    for forbidden in (
        "192.168.",
        "100.125.",
        "ts.net",
        "/Users/",
        "C:\\Users",
        "hostname",
        "endpoint",
        "pid",
        "token",
        "secret",
    ):
        assert forbidden not in body


def test_old_observation_is_marked_stale():
    observed = (datetime.now(UTC) - timedelta(minutes=8)).isoformat()
    raw, headers = _signed(_sample(observed_at=observed), nonce="nonce-stale-obs1")
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 202
    live = client.get("/api/v1/live", auth=AUTH).json()
    assert live["status"] == "stale"
    assert live["freshness_s"] >= 470


def test_invalid_state_values_and_nonfinite_numbers_rejected():
    payload = _sample()
    payload["nodes"][0]["status"] = "god-mode"
    payload["links"][0]["latency_ms"] = float("nan")
    raw, headers = _signed(payload, nonce="nonce-invalid-001")
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 422


def test_node_freshness_is_reported_as_a_number_not_a_bucket():
    """The band helpers are deleted; a dead feed is distinguished by its value.

    _freshness_band existed so a clamped two-day outage would not render like a
    61-second lag. With the real `freshness_s` exposed, the distinction is in
    the data itself and needs no bucketing to survive.
    """
    raw, headers = _signed(_sample(), nonce="nonce-freshness01")
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 202

    node = client.get("/api/v1/live").json()["nodes"][0]
    assert node["freshness_s"] == 2.1
    assert not hasattr(live_telemetry, "_freshness_band")
    assert not hasattr(live_telemetry, "_latency_band")
    assert not hasattr(live_telemetry, "_activity_band")

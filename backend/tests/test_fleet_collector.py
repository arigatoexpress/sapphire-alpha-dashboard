from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from telemetry.fleet_collector import build_payload, signed_headers


def _state() -> dict:
    return {
        "generated_at": "2026-07-30T23:52:16+00:00",
        "leases": [],
        "gates": [
            {
                "id": 7,
                "title": "review exact release",
                "age_hours": 1.25,
                "status": "open",
            }
        ],
        "counts": {"leases": 0, "gates_open": 1},
    }


def test_build_payload_maps_only_the_sanitized_fleet_contract():
    payload = build_payload(_state(), sequence=99)
    assert payload == {
        "version": 1,
        "generated_at": "2026-07-30T23:52:16+00:00",
        "sequence": 99,
        "leases": [],
        "gates": [
            {
                "id": 7,
                "title": "review exact release",
                "age_hours": 1.25,
                "status": "open",
            }
        ],
        "counts": {"leases": 0, "gates_open": 1},
    }


def test_collector_rejects_extra_fields_and_false_counts():
    with pytest.raises(ValueError, match="fields"):
        build_payload({**_state(), "database_path": "/private/fleet.db"})
    with pytest.raises(ValueError, match="counts"):
        build_payload({**_state(), "counts": {"leases": 9, "gates_open": 1}})


def test_signed_headers_cover_timestamp_nonce_and_exact_body():
    body = json.dumps(
        build_payload(_state(), sequence=99), separators=(",", ":")
    ).encode()
    secret = "collector-secret-that-is-long-enough"
    headers = signed_headers(
        body,
        secret,
        timestamp=123,
        nonce="fleet-nonce-00001",
    )
    expected = hmac.new(
        secret.encode(),
        b"123.fleet-nonce-00001." + body,
        hashlib.sha256,
    ).hexdigest()
    assert headers["X-Sapphire-Signature"] == expected

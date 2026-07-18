from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from telemetry.moss_collector import build_payload, signed_headers


def _state() -> dict:
    return {
        "version": 1,
        "chainId": 4326,
        "identityHint": "0x1111…1111",
        "eth": "0.0042",
        "usdm": "188.25",
        "blockNumber": "2748",
        "observedAt": "2026-07-18T00:00:00.000Z",
    }


def test_build_payload_maps_only_the_masked_observer_contract():
    payload = build_payload(_state(), sequence=99)
    assert payload == {
        "version": 1,
        "observed_at": "2026-07-18T00:00:00.000Z",
        "sequence": 99,
        "chain": "MegaETH Mainnet",
        "identity_masked": "0x1111…1111",
        "usdm": "188.25",
        "eth": "0.0042",
        "block": "2748",
    }
    assert "source" not in payload
    assert "address" not in payload


def test_collector_rejects_full_identity_and_wrong_chain():
    with pytest.raises(ValueError, match="masked"):
        build_payload({**_state(), "identityHint": "0x1111111111111111111111111111111111111111"})
    with pytest.raises(ValueError, match="chain"):
        build_payload({**_state(), "chainId": 1})


def test_signed_headers_cover_timestamp_nonce_and_exact_body():
    body = json.dumps(build_payload(_state(), sequence=99), separators=(",", ":")).encode()
    secret = "collector-secret-that-is-long-enough"
    headers = signed_headers(body, secret, timestamp=123, nonce="moss-nonce-000001")
    expected = hmac.new(secret.encode(), b"123.moss-nonce-000001." + body, hashlib.sha256).hexdigest()
    assert headers["X-Sapphire-Signature"] == expected

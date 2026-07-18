"""Golden contract for private MOSS ingest and privacy-safe public projection."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_USERNAME"] = "testuser"
os.environ["AUTH_PASSWORD"] = "testpass-strong-99"

import main
from main import app


client = TestClient(app)
AUTH = ("testuser", "testpass-strong-99")
SECRET = "moss-telemetry-test-secret-long-enough"


def _sample(*, sequence: int = 42) -> dict:
    return {
        "version": 1,
        "observed_at": datetime.now(UTC).isoformat(),
        "sequence": sequence,
        "chain": "MegaETH Mainnet",
        "identity_masked": "0x1111…1111",
        "usdm": "188.25",
        "eth": "0.0042",
        "block": "2748",
    }


def _signed(payload: dict, *, nonce: str = "moss-nonce-000001") -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    message = timestamp.encode() + b"." + nonce.encode() + b"." + raw
    signature = hmac.new(SECRET.encode(), message, hashlib.sha256).hexdigest()
    return raw, {
        "Content-Type": "application/json",
        "X-Sapphire-Timestamp": timestamp,
        "X-Sapphire-Nonce": nonce,
        "X-Sapphire-Signature": signature,
    }


@pytest.fixture(autouse=True)
def moss_state(monkeypatch):
    monkeypatch.setenv("MOSS_TELEMETRY_INGEST_SECRET", SECRET)
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    monkeypatch.setenv("PUBLIC_TELEMETRY_DELAY_SECONDS", "0")
    main._reset_moss_telemetry_for_tests()
    yield
    main._reset_moss_telemetry_for_tests()


def test_signed_ingest_preserves_exact_operator_decimal_strings():
    raw, headers = _signed(_sample())
    accepted = client.post("/api/v1/moss/telemetry", content=raw, headers=headers)
    assert accepted.status_code == 202

    operator = client.get("/api/v1/moss", auth=AUTH).json()
    assert operator["status"] == "live"
    assert operator["public_view"] is False
    assert operator["identity_masked"] == "0x1111…1111"
    assert operator["usdm"] == "188.25"
    assert operator["eth"] == "0.0042"
    assert operator["block"] == "2748"


def test_public_projection_bands_capital_and_removes_fingerprinting_tuple():
    raw, headers = _signed(_sample(), nonce="moss-nonce-public1")
    assert client.post("/api/v1/moss/telemetry", content=raw, headers=headers).status_code == 202

    public = client.get("/api/v1/moss").json()
    body = json.dumps(public)
    assert public["public_view"] is True
    assert public["network"] == "MegaETH"
    assert public["usdm_band"] == "$100–$249"
    assert public["eth_state"] == "present"
    assert public["observation_freshness"] == "current"
    assert "identity_masked" not in public
    for forbidden in ("0x1111", "188.25", "0.0042", "2748", "block"):
        assert forbidden not in body


@pytest.mark.parametrize(
    "poison",
    [
        {"identity_masked": "0x1111111111111111111111111111111111111111"},
        {"source": "https://mainnet.megaeth.com/rpc"},
        {"chain": "Ethereum Mainnet"},
        {"usdm": "-1"},
    ],
)
def test_contract_rejects_full_addresses_internal_sources_wrong_chain_and_bad_units(poison):
    payload = {**_sample(), **poison}
    raw, headers = _signed(payload, nonce=f"moss-poison-{len(json.dumps(poison))}")
    assert client.post("/api/v1/moss/telemetry", content=raw, headers=headers).status_code == 422


def test_bad_signature_fails_closed_and_empty_state_is_honest():
    empty = client.get("/api/v1/moss").json()
    assert empty["status"] == "offline"
    assert empty["usdm_band"] == "not observed"

    raw, headers = _signed(_sample(), nonce="moss-badsig-0001")
    headers["X-Sapphire-Signature"] = "0" * 64
    assert client.post("/api/v1/moss/telemetry", content=raw, headers=headers).status_code == 401

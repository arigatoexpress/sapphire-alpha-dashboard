"""Golden evals for the Machine Room: un-redacted reads, still-protected writes.

Written before the refactor, per the charter (evals are the spec). Three
invariants live here, and each one is load-bearing:

1.  **Reads are un-redacted.** `GET /api/v1/live` anonymously returns the real
    numbers. The redaction tier is gone, so no `*_band`, `public_view`, or
    `public_policy` key may survive anywhere in the response tree.
2.  **Capital is still banded.** MOSS keeps `usdm_band` and never exposes raw
    `usdm`. This is Ari's D1 line and it is deliberate, not an oversight — the
    test exists so a future cleanup that "finishes the job" fails loudly.
3.  **Un-redacting reads did not un-protect writes.** Non-GET without
    credentials still 401s; ingest still rejects a bad HMAC.

Plus the cadence-parity check that fixes the staleness bug as a *class*: the
publisher interval and the staleness threshold are two constants in two files
that must agree, so the test reads the real interval out of the real plist
rather than keeping a third copy of the number.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import plistlib
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

os.environ["AUTH_USERNAME"] = "testuser"
os.environ["AUTH_PASSWORD"] = "testpass-strong-99"

import live_telemetry
import main
import moss_telemetry
from main import app


ROOT = Path(__file__).resolve().parents[2]
PLIST = ROOT / "infra" / "com.sapphire.alpha-telemetry-publisher.plist"

client = TestClient(app)
AUTH = ("testuser", "testpass-strong-99")
SECRET = "telemetry-test-secret-that-is-long-enough"
MOSS_SECRET = "moss-telemetry-test-secret-long-enough"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _walk(node: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    """Yield every (json-path, value) pair in a decoded JSON tree."""
    if isinstance(node, dict):
        for key, child in node.items():
            here = f"{path}.{key}"
            yield here, child
            yield from _walk(child, here)
    elif isinstance(node, list):
        for index, child in enumerate(node):
            here = f"{path}[{index}]"
            yield here, child
            yield from _walk(child, here)


def _keys_anywhere(tree: Any) -> list[str]:
    return [
        path.rsplit(".", 1)[-1]
        for path, _ in _walk(tree)
        if not path.rsplit(".", 1)[-1].endswith("]")
    ]


def _sample_live(*, sequence: int = 4242) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "version": 1,
        "observed_at": now,
        "sequence": sequence,
        "summary": {
            "state": "observing",
            "active_agents": 3,
            "events_per_min": 37.2,
            "verified_today": 12,
            "attention": 0,
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
            "decision_gate": "manual",
            "execution": "off",
        },
        "events": [
            {
                "id": "evt-4242",
                "observed_at": now,
                "event_class": "agent",
                "source": "intelligence",
                "target": "archive",
                "label": "Research result verified",
                "status": "verified",
            }
        ],
    }


def _sign(payload: dict[str, Any], secret: str, *, nonce: str) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    message = ts.encode() + b"." + nonce.encode() + b"." + raw
    return raw, {
        "Content-Type": "application/json",
        "X-Sapphire-Timestamp": ts,
        "X-Sapphire-Nonce": nonce,
        "X-Sapphire-Signature": hmac.new(secret.encode(), message, hashlib.sha256).hexdigest(),
    }


@pytest.fixture(autouse=True)
def _telemetry_state(monkeypatch):
    monkeypatch.setenv("TELEMETRY_INGEST_SECRET", SECRET)
    monkeypatch.setenv("MOSS_TELEMETRY_INGEST_SECRET", MOSS_SECRET)
    monkeypatch.delenv("PUBLIC_TELEMETRY_DELAY_SECONDS", raising=False)
    main._reset_live_telemetry_for_tests()
    main._reset_moss_telemetry_for_tests()
    yield
    main._reset_live_telemetry_for_tests()
    main._reset_moss_telemetry_for_tests()


# --------------------------------------------------------------------------
# 1. reads are un-redacted
# --------------------------------------------------------------------------


def test_anonymous_live_returns_the_real_numbers():
    raw, headers = _sign(_sample_live(), SECRET, nonce="nonce-machineroom01")
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 202

    public = client.get("/api/v1/live")
    assert public.status_code == 200
    body = public.json()

    # the exact figures the producer measured, not adjectives
    assert body["summary"]["events_per_min"] == 37.2
    assert body["links"][0]["latency_ms"] == 7.4
    assert body["links"][0]["event_rate"] == 18.0
    assert body["nodes"][0]["load"] == "low"
    assert body["nodes"][0]["activity_rate"] == 8.0
    assert body["nodes"][0]["freshness_s"] == 2.1
    assert isinstance(body["freshness_s"], float)
    assert body["status"] == "live"


def test_anonymous_live_matches_the_operator_view_exactly():
    """No second tier means no divergence to describe."""
    raw, headers = _sign(_sample_live(), SECRET, nonce="nonce-machineroom02")
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 202

    volatile = {"served_at", "freshness_s"}
    anon = {k: v for k, v in client.get("/api/v1/live").json().items() if k not in volatile}
    operator = {
        k: v for k, v in client.get("/api/v1/live", auth=AUTH).json().items() if k not in volatile
    }
    assert anon == operator


def test_no_redaction_key_survives_anywhere_in_the_live_tree():
    raw, headers = _sign(_sample_live(), SECRET, nonce="nonce-machineroom03")
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 202

    body = client.get("/api/v1/live").json()
    banded = [key for key in _keys_anywhere(body) if key.endswith("_band")]
    assert banded == [], f"redaction keys survived: {banded}"
    assert "public_view" not in _keys_anywhere(body)
    assert "public_policy" not in _keys_anywhere(body)


def test_empty_live_snapshot_is_also_unredacted():
    """The offline shape is a snapshot too — it must not reintroduce the tier."""
    body = client.get("/api/v1/live").json()
    assert body["status"] == "offline"
    assert [key for key in _keys_anywhere(body) if key.endswith("_band")] == []
    assert "public_view" not in _keys_anywhere(body)
    assert "public_policy" not in _keys_anywhere(body)


def test_public_projection_is_gone_from_live_telemetry():
    """Deleted, not merely unused — a dormant redactor invites reintroduction."""
    assert not hasattr(live_telemetry, "public_projection")


def test_legacy_stored_snapshot_is_normalized_on_read():
    """Snapshots already in Firestore carry `load_band`; reads must not leak it.

    Exercised through the read path rather than by calling the helper, so that
    deleting the call — not just the helper — fails the test.
    """
    legacy = live_telemetry.validate_snapshot(_sample_live(sequence=99))
    for node in legacy["nodes"]:
        node["load_band"] = node.pop("load")

    persistence = live_telemetry.MemoryTelemetryPersistence()
    persistence.accept(legacy, nonce="legacy-nonce-001", received_at=time.time())
    served = live_telemetry.LiveTelemetryStore(persistence).get()

    assert served["nodes"][0]["load"] == "low"
    assert [key for key in _keys_anywhere(served) if key.endswith("_band")] == []


# --------------------------------------------------------------------------
# 2. capital stays banded (Ari D1) — this test must fail loudly if "finished"
# --------------------------------------------------------------------------


def test_moss_capital_stays_banded_for_anonymous_readers():
    payload = {
        "version": 1,
        "observed_at": datetime.now(UTC).isoformat(),
        "sequence": 7,
        "chain": "MegaETH Mainnet",
        "identity_masked": "0x1111…1111",
        "usdm": "189.70",
        "eth": "0.0042",
        "block": "2748",
    }
    raw, headers = _sign(payload, MOSS_SECRET, nonce="nonce-mossband0001")
    accepted = client.post("/api/v1/moss/telemetry", content=raw, headers=headers)
    assert accepted.status_code == 202, accepted.text

    body = client.get("/api/v1/moss").json()
    assert body["usdm_band"] == "$100–$249"
    assert "usdm" not in body, "raw capital must never reach an anonymous reader"
    assert "189.7" not in json.dumps(body)


def test_moss_public_projection_still_exists():
    """The MOSS redactor is the one that stays. Deleting it is the regression."""
    assert hasattr(moss_telemetry, "public_projection")
    assert hasattr(moss_telemetry, "_usdm_band")


# --------------------------------------------------------------------------
# 3. writes are still protected
# --------------------------------------------------------------------------


def _request(method: str) -> Request:
    return Request({"type": "http", "method": method, "path": "/api/v1/live", "headers": []})


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_non_get_without_credentials_is_rejected(method):
    """Asserted against the dependency, not over HTTP.

    Every route that uses `auth_or_public` happens to be GET-only, so an
    anonymous POST returns 405 from the router before auth is ever consulted.
    A status-code test at the HTTP layer therefore passes even if the gate is
    removed entirely — it measures the routing table, not the gate. Calling the
    dependency directly is the only way this assertion can actually fail.
    """
    with pytest.raises(HTTPException) as raised:
        main.auth_or_public(_request(method), credentials=None)
    assert raised.value.status_code == 401
    assert raised.value.headers.get("WWW-Authenticate") == "Basic"


def test_anonymous_get_is_allowed_by_the_same_dependency():
    """The other half of the contract, so the test above cannot pass vacuously."""
    assert main.auth_or_public(_request("GET"), credentials=None) == main.PUBLIC_USER


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_non_get_over_http_never_succeeds_anonymously(method):
    response = getattr(client, method)("/api/v1/live")
    assert response.status_code in (401, 405)


def test_live_ingest_still_rejects_a_bad_hmac():
    raw, headers = _sign(_sample_live(), SECRET, nonce="nonce-badhmac00001")
    headers["X-Sapphire-Signature"] = "0" * 64
    assert client.post("/api/v1/telemetry", content=raw, headers=headers).status_code == 401


def test_live_ingest_still_rejects_an_unsigned_body():
    raw = json.dumps(_sample_live(), separators=(",", ":")).encode()
    response = client.post(
        "/api/v1/telemetry", content=raw, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 401


def test_moss_ingest_still_rejects_a_bad_hmac():
    payload = {
        "version": 1,
        "observed_at": datetime.now(UTC).isoformat(),
        "sequence": 8,
        "chain": "MegaETH Mainnet",
        "identity_masked": "0x1111…1111",
        "usdm": "189.70",
        "eth": "0.0042",
        "block": "2748",
    }
    raw, headers = _sign(payload, MOSS_SECRET, nonce="nonce-mossbad00001")
    headers["X-Sapphire-Signature"] = "f" * 64
    assert client.post("/api/v1/moss/telemetry", content=raw, headers=headers).status_code == 401


def test_raw_vault_map_still_requires_auth():
    assert client.get("/vault/rag-map").status_code == 401


# --------------------------------------------------------------------------
# 4. cadence parity — the staleness bug, fixed as a class
# --------------------------------------------------------------------------


def _publisher_interval_seconds() -> int:
    with PLIST.open("rb") as handle:
        return int(plistlib.load(handle)["StartInterval"])


def test_publisher_cadence_leaves_margin_under_the_staleness_threshold():
    """The feed went stale for 120s of every 300s cycle because these two
    constants were set independently. One missed publish must not flip the
    dashboard to `stale`, so the threshold has to cover two whole cycles.

    Note the direction of the fix: shorten the cadence. Raising
    DEFAULT_STALE_AFTER_SECONDS would make this pass while turning the
    freshness check into a green light that never fires.
    """
    interval = _publisher_interval_seconds()
    threshold = live_telemetry.DEFAULT_STALE_AFTER_SECONDS
    assert interval * 2 < threshold, (
        f"publisher runs every {interval}s but telemetry is called stale after "
        f"{threshold}s; a single missed publish flips the dashboard to stale"
    )


def test_staleness_threshold_is_short_enough_to_mean_something():
    """Guards the forbidden fix from the other side: a threshold raised until it
    never fires is no check at all. Ten minutes is the outer bound of useful."""
    assert live_telemetry.DEFAULT_STALE_AFTER_SECONDS <= 600


def test_repo_plist_matches_the_installed_launchagent():
    """`infra/` is the source of truth; the installed copy must not drift.

    Skipped where the LaunchAgent is not installed (CI, Cloud Build), so this
    catches drift on the projector host without failing elsewhere.
    """
    installed = Path.home() / "Library/LaunchAgents/com.sapphire.alpha-telemetry-publisher.plist"
    if not installed.exists():
        pytest.skip("publisher LaunchAgent is not installed on this host")
    with installed.open("rb") as handle:
        live = plistlib.load(handle)
    with PLIST.open("rb") as handle:
        repo = plistlib.load(handle)
    assert live == repo, (
        "installed LaunchAgent has drifted from infra/; reinstall it with "
        "launchctl unload/load so the cadence in the repo is the cadence that runs"
    )

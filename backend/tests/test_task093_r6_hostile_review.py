"""Task 093 R6 regressions for the distinct R5 hostile review."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import main
from moss_telemetry import MossTelemetryStore


NOW = datetime.now(UTC) - timedelta(seconds=5)
OLD = NOW - timedelta(days=3)


class _FixedPersistence:
    def __init__(self, snapshot: Any, *, received_at: float | None = None):
        self.snapshot = snapshot
        self.received_at = NOW.timestamp() if received_at is None else received_at

    def select(self, *, received_before: float) -> tuple[float, Any]:
        return self.received_at, self.snapshot

    def has_history(self) -> bool:
        return True

    def reset(self) -> None:
        raise AssertionError("read-only hostile persistence")


def _moss_snapshot(*, observed_at: str) -> dict[str, Any]:
    return {
        "version": 1,
        "observed_at": observed_at,
        "sequence": 1,
        "chain": "MegaETH Mainnet",
        "identity_masked": "0x1111…1111",
        "usdm": "188.25",
        "eth": "0.0042",
        "block": "2748",
    }


@pytest.mark.parametrize(
    "snapshot,received_at",
    [
        ({"observed_at": "malformed"}, NOW.timestamp()),
        (_moss_snapshot(observed_at=NOW.isoformat()), float("nan")),
        (_moss_snapshot(observed_at=NOW.isoformat()), float("inf")),
    ],
)
def test_unverifiable_durable_moss_fails_canonical_offline(
    snapshot: Any,
    received_at: float,
) -> None:
    store = MossTelemetryStore(
        _FixedPersistence(snapshot, received_at=received_at)
    )

    for public in (True, False):
        projected = store.get(public=public, now=NOW.timestamp() + 10)
        assert projected["status"] == "offline"
        assert projected["observed_at"] is None
        assert "identity_masked" not in projected
        assert "usdm" not in projected
        assert "eth" not in projected
        assert "block" not in projected


def test_future_durable_moss_never_projects_live() -> None:
    future = (NOW + timedelta(seconds=30)).isoformat()
    store = MossTelemetryStore(
        _FixedPersistence(_moss_snapshot(observed_at=future))
    )

    for public in (True, False):
        projected = store.get(public=public, now=NOW.timestamp())
        assert projected["status"] == "offline"
        assert projected["observed_at"] is None
        assert "identity_masked" not in projected
        assert "usdm" not in projected


def test_stale_moss_withdraws_all_money_and_identity_claims() -> None:
    store = MossTelemetryStore(
        _FixedPersistence(_moss_snapshot(observed_at=OLD.isoformat()))
    )

    public = store.get(public=True, now=NOW.timestamp())
    assert public["status"] == "stale"
    assert public["usdm_band"] == "not observed"
    assert public["eth_state"] == "not observed"

    private = store.get(public=False, now=NOW.timestamp())
    assert private["status"] == "stale"
    for field in ("identity_masked", "usdm", "eth", "block", "chain", "sequence"):
        assert field not in private


def test_bounded_json_decoder_rejects_overflow_anywhere() -> None:
    for payload in (
        b'{"value":1e999}',
        b'{"nested":[{"value":-1e999}]}',
    ):
        with pytest.raises(ValueError):
            main._decode_bounded_json(payload, max_bytes=1024)


@pytest.mark.parametrize(
    "limits",
    [
        {"daily": 10},
        {"per_order_cap_pct": 101},
        {"per_order_cap_pct": -1},
        {"max_daily_usd": 1_000_000_001},
        {"per_order_cap_pct": float("nan")},
    ],
)
def test_invalid_nested_skin_limits_withdraw_entire_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limits: dict[str, Any],
) -> None:
    payload = {
        "observed_at": NOW.isoformat(),
        "mode": "bounded_auto",
        "deployed_usd": 1,
        "n_open": 1,
        "positions": [],
        "fills": [],
        "skin_in_game": True,
        "limits": limits,
    }
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", tmp_path)
    (tmp_path / "skin-book.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    wallet = main._wallet_status(now=NOW)

    assert wallet["updated_at"] is None
    assert wallet["deployed_usd"] is None
    assert wallet["n_open"] is None
    assert wallet["limits"] == {}
    assert not any(
        isinstance(value, float) and not math.isfinite(value)
        for value in wallet.values()
    )


def _research_packet(*, observed_at: str | None = None) -> list[dict[str, Any]]:
    sources = ("benjamin_cowen", "arthur_hayes", "bankless", "limitless")
    packet = [
        {
            "id": f"clip-{index}",
            "title": f"Reviewed claim {index}",
            "source": source,
            "observed_at": observed_at or NOW.isoformat(),
        }
        for index, source in enumerate(sources, start=1)
    ]
    return packet


@pytest.mark.parametrize(
    "mutation",
    ["missing", "malformed", "future", "stale"],
)
def test_research_requires_one_strict_current_observed_at(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    packet = _research_packet()
    if mutation == "missing":
        packet[0].pop("observed_at")
    elif mutation == "malformed":
        packet[0]["observed_at"] = "not-a-time"
    elif mutation == "future":
        packet[0]["observed_at"] = (NOW + timedelta(minutes=10)).isoformat()
    else:
        packet[0]["observed_at"] = OLD.isoformat()
    monkeypatch.setenv("DASHBOARD_RESEARCH_CLIPS_JSON", json.dumps(packet))

    feed = main._research_feed(now=NOW)

    assert all(clip["id"] != "clip-1" for clip in feed["clips"])
    assert feed["live"] is False


def test_duplicate_research_json_fails_entire_feed_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = json.dumps(NOW.isoformat())
    payload = (
        '[{"id":"one","title":"claim","source":"benjamin_cowen",'
        f'"observed_at":"malformed","observed_at":{now}}},'
        '{"id":"two","title":"claim","source":"arthur_hayes",'
        f'"observed_at":{now}}},'
        '{"id":"three","title":"claim","source":"bankless",'
        f'"observed_at":{now}}},'
        '{"id":"four","title":"claim","source":"limitless",'
        f'"observed_at":{now}}}]'
    )
    monkeypatch.setenv("DASHBOARD_RESEARCH_CLIPS_JSON", payload)

    assert main._research_feed(now=NOW)["clips"] == []


def test_current_research_exposes_source_age(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DASHBOARD_RESEARCH_CLIPS_JSON",
        json.dumps(_research_packet()),
    )

    feed = main._research_feed(now=NOW + timedelta(seconds=5))
    public = main._public_research(feed)

    assert feed["live"] is True
    assert {clip["age_s"] for clip in feed["clips"]} == {5.0}
    assert {clip["age_s"] for clip in public["clips"]} == {5.0}

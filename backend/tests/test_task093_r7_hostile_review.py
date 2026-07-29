"""Task 093 R7 goldens for the exact sealed R6 hostile review.

All probes are local and read-only. They use temporary files or in-memory
persistence and cannot reach a provider, wallet, broker, trade, pause, or
deployment surface.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import main
from moss_telemetry import MossTelemetryStore


NOW = datetime.now(UTC) - timedelta(seconds=5)


class _FixedPersistence:
    def __init__(self, snapshot: Any, *, received_at: float) -> None:
        self.snapshot = snapshot
        self.received_at = received_at

    def select(self, *, received_before: float) -> tuple[float, Any]:
        return self.received_at, self.snapshot

    def has_history(self) -> bool:
        return True

    def reset(self) -> None:
        raise AssertionError("read-only hostile persistence")


def _moss_snapshot() -> dict[str, Any]:
    return {
        "version": 1,
        "observed_at": NOW.isoformat(),
        "sequence": 1,
        "chain": "MegaETH Mainnet",
        "identity_masked": "0x1111…1111",
        "usdm": "188.25",
        "eth": "0.0042",
        "block": "2748",
    }


@pytest.mark.parametrize(
    "received_at",
    [
        (NOW + timedelta(seconds=60)).timestamp(),
        (NOW - timedelta(days=1)).timestamp(),
    ],
)
def test_moss_rejects_temporally_impossible_durable_receipt(
    received_at: float,
) -> None:
    store = MossTelemetryStore(
        _FixedPersistence(_moss_snapshot(), received_at=received_at)
    )

    for public in (True, False):
        projected = store.get(
            public=public,
            now=(NOW + timedelta(seconds=10)).timestamp(),
        )
        assert projected["status"] == "offline"
        assert projected["observed_at"] is None
        assert "received_at" not in projected


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def test_huge_gate_integer_fails_closed_instead_of_raising(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rh_dir = tmp_path / "rh-chain"
    pause_dir = tmp_path / "pause"
    rh_dir.mkdir(mode=0o700)
    pause_dir.mkdir(mode=0o700)
    mac_pause = pause_dir / "mac.json"
    rh_pause = pause_dir / "rh.json"
    clear = {"state": "clear", "observed_at": NOW.isoformat()}
    _write_json(mac_pause, clear)
    _write_json(rh_pause, clear)
    gate_path = rh_dir / "gate.json"
    gate_path.write_text(
        (
            '{"observed_at":'
            + json.dumps(NOW.isoformat())
            + ',"mode":"bounded_auto","armed":true,"cap_usd":'
            + ("9" * 1_000)
            + "}"
        ),
        encoding="utf-8",
    )
    gate_path.chmod(0o600)
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", rh_dir)
    monkeypatch.setattr(
        main,
        "_PAUSE_SENTINELS",
        {"mac": mac_pause, "rh_chain": rh_pause},
    )

    projected = main._gate_status(now=NOW)

    assert projected["state"] == "unavailable"
    assert projected["armed"] is None
    assert projected["mode"] == "unavailable"
    assert projected["cap_usd"] is None


def _research_packet() -> list[dict[str, Any]]:
    return [
        {
            "id": f"clip-{index}",
            "title": f"Unverified text {index}",
            "source": source,
            "observed_at": NOW.isoformat(),
        }
        for index, source in enumerate(
            ("benjamin_cowen", "arthur_hayes", "bankless", "limitless"),
            start=1,
        )
    ]


def test_research_byte_limit_applies_before_whitespace_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = json.dumps(_research_packet())
    oversized = (" " * (main._MAX_RESEARCH_DOCUMENT_BYTES + 1)) + packet
    monkeypatch.setenv("DASHBOARD_RESEARCH_CLIPS_JSON", oversized)

    feed = main._research_feed(now=NOW)

    assert feed["clips"] == []
    assert feed["live"] is False


def test_unproven_research_withdraws_review_and_primary_source_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DASHBOARD_RESEARCH_CLIPS_JSON",
        json.dumps(_research_packet()),
    )

    feed = main._research_feed(now=NOW)
    public = main._public_research(feed)

    assert feed["clips"]
    assert feed["live"] is False
    assert feed["policy"]["rules"]["review_status"] == "unverified"
    assert "minimum_independent_primary_sources" not in feed["policy"]["rules"]
    assert public["live"] is False
    assert public["policy"]["review_status"] == "unverified"
    assert "minimum_independent_checks" not in public["policy"]

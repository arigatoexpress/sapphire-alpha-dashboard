"""Task 093 R3 goldens for the sealed R2 hostile-review findings.

Every probe is local and source-only.  No provider, service, credential,
message, broker, wallet, order, or trade adapter is reachable from this file.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import live_telemetry
import local_dashboard_server
import main
from live_telemetry import (
    LiveTelemetryStore,
    MemoryTelemetryPersistence,
    validate_snapshot,
)
from tests.test_live_telemetry import _sample


NOW = datetime(2026, 7, 28, 23, 30, tzinfo=UTC)


def _store(snapshot: dict) -> LiveTelemetryStore:
    persistence = MemoryTelemetryPersistence()
    persistence.accept(
        validate_snapshot(snapshot),
        nonce="task093-r3-hostile",
        received_at=NOW.timestamp(),
    )
    return LiveTelemetryStore(persistence)


@pytest.mark.parametrize(
    "document",
    [
        {
            "state": "clear",
            "observed_at": "not-a-timestamp",
            "updated_at": NOW.isoformat(),
        },
        {
            "state": "clear",
            "observed_at": NOW.isoformat(),
            "updated_at": NOW.isoformat(),
        },
        {
            "state": "clear",
            "observed_at": NOW.isoformat(),
            "updated_at": (NOW - timedelta(seconds=1)).isoformat(),
        },
        {
            "state": "clear",
            "updated_at": NOW.isoformat(),
        },
    ],
)
def test_pause_clear_has_one_strict_semantic_timestamp(
    tmp_path: Path,
    document: dict[str, str],
) -> None:
    observations = []
    for source in ("mac", "rh_chain"):
        candidate = tmp_path / f"{source}.json"
        candidate.write_text(json.dumps(document), encoding="utf-8")
        observations.append(main._pause_file_observation(source, candidate))

    assert observations == [
        {"source": "mac", "state": "invalid", "observed_at": None},
        {"source": "rh_chain", "state": "invalid", "observed_at": None},
    ]
    assert main._evaluate_pause_truth(observations, now=NOW) == {
        "state": "unknown",
        "clear": None,
        "observed_at": None,
    }


def test_pause_legacy_active_and_explicit_active_remain_fail_safe(
    tmp_path: Path,
) -> None:
    legacy = tmp_path / "legacy-active.json"
    explicit = tmp_path / "explicit-active.json"
    legacy.write_text(json.dumps({"created_at": NOW.isoformat()}), encoding="utf-8")
    explicit.write_text(
        json.dumps({"state": "active", "observed_at": NOW.isoformat()}),
        encoding="utf-8",
    )

    assert main._pause_file_observation("mac", legacy)["state"] == "active"
    assert main._pause_file_observation("rh_chain", explicit)["state"] == "active"


def test_local_fallback_absence_never_collects_or_fabricates_freshness(
    tmp_path: Path,
) -> None:
    projected = local_dashboard_server._build_live_snapshot(
        snapshot_path=tmp_path / "absent.json",
        now=NOW.timestamp(),
    )

    assert projected["status"] == "offline"
    assert projected["observed_at"] is None
    assert projected["freshness_s"] is None
    assert projected["summary"]["active_agents"] is None
    assert projected["markets"]["status"] == "offline"


def test_local_fallback_repeated_gets_only_age_one_persisted_snapshot(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "live-snapshot.json"
    candidate.write_text(
        json.dumps(_sample(observed_at=NOW.isoformat(), sequence=9304)),
        encoding="utf-8",
    )
    candidate.chmod(0o600)
    source_before = candidate.read_bytes()
    stat_before = candidate.stat()

    first = local_dashboard_server._build_live_snapshot(
        snapshot_path=candidate,
        now=(NOW + timedelta(seconds=10)).timestamp(),
    )
    second = local_dashboard_server._build_live_snapshot(
        snapshot_path=candidate,
        now=(NOW + timedelta(seconds=40)).timestamp(),
    )

    assert first["observed_at"] == second["observed_at"] == NOW.isoformat()
    assert first["received_at"] == second["received_at"] == NOW.isoformat()
    assert second["freshness_s"] - first["freshness_s"] == 30
    assert (
        second["markets"]["feed_age_s"] - first["markets"]["feed_age_s"]
        == pytest.approx(30)
    )
    assert first["served_at"] != second["served_at"]
    stat_after = candidate.stat()
    assert candidate.read_bytes() == source_before
    assert (
        stat_after.st_mode,
        stat_after.st_uid,
        stat_after.st_gid,
        stat_after.st_nlink,
        stat_after.st_size,
        stat_after.st_mtime_ns,
        stat_after.st_ctime_ns,
    ) == (
        stat_before.st_mode,
        stat_before.st_uid,
        stat_before.st_gid,
        stat_before.st_nlink,
        stat_before.st_size,
        stat_before.st_mtime_ns,
        stat_before.st_ctime_ns,
    )


def test_local_fallback_rejects_unadmitted_snapshot_objects(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text(
        json.dumps(_sample(observed_at=NOW.isoformat(), sequence=9305)),
        encoding="utf-8",
    )
    target.chmod(0o600)
    symlink = tmp_path / "symlink.json"
    os.symlink(target, symlink)
    hardlink = tmp_path / "hardlink.json"
    os.link(target, hardlink)
    fifo = tmp_path / "snapshot.fifo"
    os.mkfifo(fifo)

    for candidate in (
        symlink,
        hardlink,
        fifo,
        Path(os.devnull),
    ):
        projected = local_dashboard_server._build_live_snapshot(
            snapshot_path=candidate,
            now=NOW.timestamp(),
        )
        assert projected["status"] == "offline"
        assert projected["observed_at"] is None
        assert projected["freshness_s"] is None


def test_current_parent_withdraws_expired_tracks_and_all_epistemic_claims() -> None:
    sample = _sample(observed_at=NOW.isoformat(), sequence=9306)
    sample["desk"]["updated_at"] = NOW.isoformat()
    sample["desk"]["tracks"][0]["freshness_s"] = 400
    sample["desk"]["tracks"][1]["freshness_s"] = 10
    sample["desk"]["epistemics"]["updated_ts"] = (NOW - timedelta(hours=1)).timestamp()
    sample["desk"]["epistemics"]["learning"]["updated_ts"] = (
        NOW - timedelta(hours=1)
    ).timestamp()

    projected = _store(sample).get(
        now=(NOW + timedelta(seconds=10)).timestamp(),
        stale_after_seconds=180,
    )

    assert projected["status"] == "live"
    assert [track["strategy"] for track in projected["desk"]["tracks"]] == ["equity"]
    assert projected["desk"]["epistemics"] == live_telemetry._epistemics(None)


def test_stale_only_agent_withdraws_current_active_agent_summary() -> None:
    sample = _sample(observed_at=NOW.isoformat(), sequence=9307)
    sample["summary"]["active_agents"] = 1
    sample["agents"][0]["updated_at"] = (NOW - timedelta(hours=1)).isoformat()

    projected = _store(sample).get(
        now=(NOW + timedelta(seconds=10)).timestamp(),
        stale_after_seconds=180,
    )

    assert projected["status"] == "live"
    assert projected["agents"][0]["state"] == "offline"
    assert projected["summary"]["active_agents"] is None


def test_one_expired_agent_withdraws_the_mixed_aggregate_instead_of_undercounting() -> None:
    sample = _sample(observed_at=NOW.isoformat(), sequence=9308)
    sample["summary"]["active_agents"] = 2
    sample["agents"][0]["updated_at"] = (NOW - timedelta(hours=1)).isoformat()
    sample["agents"].append(
        {
            **sample["agents"][0],
            "id": "current-agent",
            "role": "Current observer",
            "state": "working",
            "updated_at": NOW.isoformat(),
        }
    )

    projected = _store(sample).get(
        now=(NOW + timedelta(seconds=10)).timestamp(),
        stale_after_seconds=180,
    )

    assert [agent["state"] for agent in projected["agents"]] == [
        "offline",
        "working",
    ]
    # The schema can summarize agents that are not in the bounded child list.
    # Deriving "1" from the returned children would therefore be an undercount;
    # withdrawing the aggregate is the only supported exact projection.
    assert projected["summary"]["active_agents"] is None

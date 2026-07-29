"""Hostile Task 093 R1 review regressions.

These source-only tests reproduce the sealed exact-tree review without
reaching a provider, service, message transport, broker, wallet, order, or
trade adapter.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import local_dashboard_server
import main
from live_telemetry import (
    LiveTelemetryStore,
    MemoryTelemetryPersistence,
    validate_snapshot,
)
from tests.test_live_telemetry import _sample


NOW = datetime(2026, 7, 28, 23, 30, tzinfo=UTC)


def _store(snapshot: dict, *, received_at: float) -> LiveTelemetryStore:
    persistence = MemoryTelemetryPersistence()
    persistence.accept(snapshot, nonce="task093-hostile-r1", received_at=received_at)
    return LiveTelemetryStore(persistence)


def test_pause_sources_are_the_exact_two_canonical_active_sentinels() -> None:
    assert main._PAUSE_SENTINELS == {
        "mac": Path.home() / ".sapphire" / "autonomous_trading_pause",
        "rh_chain": Path.home() / "ops-state" / "rh-chain" / "killswitch",
    }


def test_pause_clear_cannot_be_fabricated_from_filesystem_mtime(
    tmp_path: Path,
) -> None:
    observations = []
    for source in ("mac", "rh_chain"):
        candidate = tmp_path / f"{source}.json"
        candidate.write_text(json.dumps({"state": "clear"}), encoding="utf-8")
        observations.append(main._pause_file_observation(source, candidate))

    resolved = main._evaluate_pause_truth(
        [item for item in observations if item is not None],
        now=NOW,
    )

    assert all(
        item == {"source": source, "state": "invalid", "observed_at": None}
        for source, item in zip(("mac", "rh_chain"), observations, strict=True)
    )
    assert resolved["state"] == "unknown"
    assert resolved["clear"] is None


def test_symlinked_pause_documents_never_clear_the_gate(tmp_path: Path) -> None:
    target = tmp_path / "attacker-controlled.json"
    target.write_text(
        json.dumps({"state": "clear", "observed_at": NOW.isoformat()}),
        encoding="utf-8",
    )
    observations = []
    for source in ("mac", "rh_chain"):
        candidate = tmp_path / f"{source}.json"
        os.symlink(target, candidate)
        observations.append(main._pause_file_observation(source, candidate))

    resolved = main._evaluate_pause_truth(
        [item for item in observations if item is not None],
        now=NOW,
    )

    assert all(
        item == {"source": source, "state": "invalid", "observed_at": None}
        for source, item in zip(("mac", "rh_chain"), observations, strict=True)
    )
    assert resolved["state"] == "unknown"
    assert resolved["clear"] is None


def test_group_or_world_writable_pause_document_is_unverifiable(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "pause.json"
    candidate.write_text(
        json.dumps({"state": "clear", "observed_at": NOW.isoformat()}),
        encoding="utf-8",
    )
    candidate.chmod(0o666)

    assert main._pause_file_observation("mac", candidate) == {
        "source": "mac",
        "state": "invalid",
        "observed_at": None,
    }


def test_fifo_pause_source_is_rejected_without_blocking(tmp_path: Path) -> None:
    candidate = tmp_path / "pause.fifo"
    os.mkfifo(candidate)
    repo = Path(__file__).parents[2]
    script = (
        "from pathlib import Path\n"
        "import main\n"
        f"result = main._pause_file_observation('mac', Path({str(candidate)!r}))\n"
        "assert result == "
        "{'source': 'mac', 'state': 'invalid', 'observed_at': None}\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo,
        env={**os.environ, "PYTHONPATH": f"{repo / 'backend'}:{repo}"},
        capture_output=True,
        text=True,
        timeout=1,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_device_pause_source_is_rejected() -> None:
    assert main._pause_file_observation("mac", Path(os.devnull)) == {
        "source": "mac",
        "state": "invalid",
        "observed_at": None,
    }


def test_hardlinked_pause_source_is_not_independent(tmp_path: Path) -> None:
    original = tmp_path / "original.json"
    alias = tmp_path / "alias.json"
    original.write_text(
        json.dumps({"state": "clear", "observed_at": NOW.isoformat()}),
        encoding="utf-8",
    )
    os.link(original, alias)

    assert main._pause_file_observation("mac", original) == {
        "source": "mac",
        "state": "invalid",
        "observed_at": None,
    }
    assert main._pause_file_observation("rh_chain", alias) == {
        "source": "rh_chain",
        "state": "invalid",
        "observed_at": None,
    }


def test_two_pause_sources_aliasing_one_inode_never_clear() -> None:
    shared_identity = (123, 456)
    observations = [
        {
            "source": source,
            "state": "clear",
            "observed_at": NOW.isoformat(),
            "_source_identity": shared_identity,
        }
        for source in ("mac", "rh_chain")
    ]

    resolved = main._evaluate_pause_truth(observations, now=NOW)

    assert resolved["state"] == "unknown"
    assert resolved["clear"] is None


def test_pause_clear_requires_two_descriptor_identities() -> None:
    observations = [
        {
            "source": source,
            "state": "clear",
            "observed_at": NOW.isoformat(),
        }
        for source in ("mac", "rh_chain")
    ]

    resolved = main._evaluate_pause_truth(observations, now=NOW)

    assert resolved["state"] == "unknown"
    assert resolved["clear"] is None


def test_duplicate_pause_json_keys_are_rejected(tmp_path: Path) -> None:
    candidate = tmp_path / "duplicate.json"
    candidate.write_text(
        (f'{{"state":"active","state":"clear","observed_at":"{NOW.isoformat()}"}}'),
        encoding="utf-8",
    )

    assert main._pause_file_observation("mac", candidate) == {
        "source": "mac",
        "state": "invalid",
        "observed_at": None,
    }


def test_symlinked_pause_parent_is_rejected(tmp_path: Path) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    candidate = real_parent / "pause.json"
    candidate.write_text(
        json.dumps({"state": "clear", "observed_at": NOW.isoformat()}),
        encoding="utf-8",
    )
    alias_parent = tmp_path / "alias"
    os.symlink(real_parent, alias_parent)

    assert main._pause_file_observation("mac", alias_parent / candidate.name) == {
        "source": "mac",
        "state": "invalid",
        "observed_at": None,
    }


def test_pause_parent_mode_drift_during_read_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    parent = tmp_path / "admitted"
    parent.mkdir(mode=0o700)
    candidate = parent / "pause.json"
    candidate.write_text(
        json.dumps({"state": "clear", "observed_at": NOW.isoformat()}),
        encoding="utf-8",
    )
    original_read = main.os.read
    changed = False

    def drifting_read(fd: int, size: int) -> bytes:
        nonlocal changed
        chunk = original_read(fd, size)
        if not changed:
            changed = True
            parent.chmod(0o755)
        return chunk

    monkeypatch.setattr(main.os, "read", drifting_read)

    assert main._pause_file_observation("mac", candidate) == {
        "source": "mac",
        "state": "invalid",
        "observed_at": None,
    }


def test_pause_file_mode_drift_during_read_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidate = tmp_path / "pause.json"
    candidate.write_text(
        json.dumps({"state": "clear", "observed_at": NOW.isoformat()}),
        encoding="utf-8",
    )
    original_read = main.os.read
    changed = False

    def drifting_read(fd: int, size: int) -> bytes:
        nonlocal changed
        chunk = original_read(fd, size)
        if not changed:
            changed = True
            candidate.chmod(0o600)
        return chunk

    monkeypatch.setattr(main.os, "read", drifting_read)

    assert main._pause_file_observation("mac", candidate) == {
        "source": "mac",
        "state": "invalid",
        "observed_at": None,
    }


def test_pause_path_replacement_during_read_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidate = tmp_path / "pause.json"
    displaced = tmp_path / "pause.displaced"
    document = json.dumps({"state": "clear", "observed_at": NOW.isoformat()})
    candidate.write_text(document, encoding="utf-8")
    original_read = main.os.read
    changed = False

    def drifting_read(fd: int, size: int) -> bytes:
        nonlocal changed
        chunk = original_read(fd, size)
        if not changed:
            changed = True
            candidate.rename(displaced)
            candidate.write_text(document, encoding="utf-8")
        return chunk

    monkeypatch.setattr(main.os, "read", drifting_read)

    assert main._pause_file_observation("mac", candidate) == {
        "source": "mac",
        "state": "invalid",
        "observed_at": None,
    }


def test_pause_path_metadata_must_match_the_read_descriptor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidate = tmp_path / "pause.json"
    candidate.write_text(
        json.dumps({"state": "clear", "observed_at": NOW.isoformat()}),
        encoding="utf-8",
    )
    original_stat = main.os.stat

    def drifted_stat(*args, **kwargs):
        observed = original_stat(*args, **kwargs)
        if kwargs.get("dir_fd") is None:
            return observed
        return SimpleNamespace(
            st_dev=observed.st_dev,
            st_ino=observed.st_ino,
            st_mode=observed.st_mode | stat.S_IWGRP,
            st_uid=observed.st_uid,
            st_gid=observed.st_gid,
            st_nlink=observed.st_nlink,
            st_size=observed.st_size,
            st_mtime_ns=observed.st_mtime_ns,
            st_ctime_ns=observed.st_ctime_ns,
        )

    monkeypatch.setattr(main.os, "stat", drifted_stat)

    assert main._pause_file_observation("mac", candidate) == {
        "source": "mac",
        "state": "invalid",
        "observed_at": None,
    }


def test_embedded_gate_pause_claims_cannot_replace_canonical_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    rh_chain = tmp_path / "rh-chain"
    rh_chain.mkdir()
    (rh_chain / "gate.json").write_text(
        json.dumps(
            {
                "armed": True,
                "mode": "bounded_auto",
                "observed_at": NOW.isoformat(),
                "pause_sources": [
                    {
                        "source": source,
                        "state": "clear",
                        "observed_at": NOW.isoformat(),
                    }
                    for source in ("mac", "rh_chain")
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", rh_chain)
    monkeypatch.setattr(
        main,
        "_PAUSE_SENTINELS",
        {
            "mac": tmp_path / "missing-mac",
            "rh_chain": tmp_path / "missing-rh-chain",
        },
    )

    gate = main._gate_status(now=NOW)

    assert gate["state"] == "unavailable"
    assert gate["pause_state"] == "unknown"
    assert gate["armed"] is None


def test_stale_parent_expires_future_skewed_agent_claim() -> None:
    observed = NOW
    sample = _sample(observed_at=observed.isoformat(), sequence=9301)
    sample["agents"][0]["updated_at"] = (observed + timedelta(seconds=50)).isoformat()
    snapshot = validate_snapshot(sample)
    store = _store(snapshot, received_at=observed.timestamp())

    result = store.get(now=(observed + timedelta(seconds=181)).timestamp())

    assert result["status"] == "stale"
    assert result["agents"][0]["state"] == "offline"
    assert result["agents"][0]["verification"] == "pending"


def test_stale_parent_withdraws_track_and_epistemic_claims() -> None:
    observed = NOW
    sample = _sample(observed_at=observed.isoformat(), sequence=9303)
    snapshot = validate_snapshot(sample)
    store = _store(snapshot, received_at=observed.timestamp())

    result = store.get(now=(observed + timedelta(seconds=181)).timestamp())

    assert result["status"] == "stale"
    assert result["desk"]["tracks"] == []
    assert result["desk"]["epistemics"] == {
        "updated_ts": None,
        "fresh": False,
        "thesis": None,
        "regime": {
            "label": "unknown",
            "fit": None,
            "data_quality": None,
            "drivers": [],
        },
        "falsifiers": [],
        "learning": {
            "status": "unavailable",
            "open": None,
            "resolved": None,
            "mean_brier": None,
            "accuracy": None,
            "lessons": 0,
            "updated_ts": None,
        },
    }


def test_local_fallback_uses_canonical_parent_aging(
    tmp_path: Path,
) -> None:
    old = NOW - timedelta(minutes=10)
    sample = _sample(observed_at=old.isoformat(), sequence=9302)
    sample["markets"]["decision_gate"] = "manual"
    sample["markets"]["execution"] = "gated"
    sample["desk"]["execution"] = "gated"
    sample["desk"]["autonomy"] = {
        "desired": "on",
        "active": True,
        "new_entries": "available",
        "reason": "stale runtime claim",
    }
    candidate = tmp_path / "live-snapshot.json"
    candidate.write_text(
        json.dumps(sample),
        encoding="utf-8",
    )
    candidate.chmod(0o600)

    projected = local_dashboard_server._build_live_snapshot(
        snapshot_path=candidate,
        now=NOW.timestamp(),
    )

    assert projected["status"] == "stale"
    assert projected["markets"]["decision_gate"] == "unknown"
    assert projected["markets"]["execution"] == "unknown"
    assert projected["desk"]["execution"] == "unknown"
    assert projected["desk"]["autonomy"]["active"] is False


def test_local_fallback_absence_is_unknown_and_readiness_is_shared() -> None:
    moss = local_dashboard_server._empty_moss_snapshot()
    fleet = local_dashboard_server._empty_fleet_counts()

    assert moss["observed_at"] is None
    assert fleet == {
        "public_view": True,
        "leases": None,
        "gates_open": None,
        "snapshot_age_s": None,
    }
    assert local_dashboard_server._runtime_readiness() == main._readiness_snapshot()


def test_stale_fleet_snapshot_withdraws_current_values() -> None:
    old = NOW - timedelta(hours=1)
    raw = {
        "generated_at": old.isoformat(),
        "leases": [
            {
                "agent": "stale-agent",
                "repo": "stale-repo",
                "purpose": "stale-purpose",
                "expires_at": old.isoformat(),
            }
        ],
        "gates": [{"id": 1, "title": "stale gate", "age_hours": 1, "status": "open"}],
    }

    projected = main._whitelist_fleet(raw, now=NOW)

    assert projected == {
        "generated_at": old.isoformat(),
        "leases": [],
        "gates": [],
        "counts": {"leases": None, "gates_open": None},
    }


def test_materially_future_fleet_snapshot_is_unverifiable() -> None:
    future = NOW + timedelta(minutes=10)
    raw = {
        "generated_at": future.isoformat(),
        "leases": [],
        "gates": [],
    }

    assert main._fleet_age_seconds(future.isoformat(), now=NOW) is None
    assert main._whitelist_fleet(raw, now=NOW) == main._EMPTY_FLEET


def test_readiness_pins_task065_source_and_negative_runtime_outcome() -> None:
    assert main._RUNTIME_READINESS["task065"] == {
        "status": "SOURCE_MERGED_INERT",
        "reviewed_head": "2d76f2a3254e5d21ca917a01f945ab1b64912aa0",
        "merged_commit": "f19270df630ef0cb67d439e00e07e70121dae4de",
        "result_sha256": (
            "5fba3c1802fa75ea49801fedb07f4a48cdeaefbe7ef8cd776621f6b8e5b5e916"
        ),
        "review_sha256": (
            "49367a90974b4c4605aa2d2c5e004c7cec9eb0841e73062d16f8bf14f2277cfc"
        ),
        "outcome": "TWO_ATTENDANCES_REQUIRED",
        "one_attendance": "ONE_ATTENDANCE_UNAVAILABLE",
        "production_execution": "PRODUCTION_EXECUTION_UNAVAILABLE",
    }


def test_public_source_copy_does_not_claim_unavailable_execution_is_running() -> None:
    repo = Path(__file__).parents[2]
    source = "\n".join(
        candidate.read_text(encoding="utf-8")
        for candidate in (
            repo / "web/src/app/architecture/page.tsx",
            repo / "web/src/app/trading/page.tsx",
            repo / "web/src/data/metrics.ts",
        )
    )
    for live_claim in (
        "runs inference, free-reign policy ticks, and order placement",
        "Both act only inside caps and designated envelopes",
        "When armed, the policy layer auto-approves",
        "GPU executor hosts the schtasks plant",
        "Model inference, free-reign plant, RH/L2 execution under caps",
    ):
        assert live_claim not in source

"""Tests for the Mac + Windows merged telemetry collector."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from live_telemetry import validate_snapshot
from telemetry.merged_collector import _load_research_projection, _merge_snapshots


def _sample_snapshot(agent_id: str, node_id: str, sequence: int) -> dict:
    return {
        "version": 1,
        "observed_at": "2026-07-23T00:00:00+00:00",
        "sequence": sequence,
        "summary": {
            "state": "observing",
            "active_agents": 1,
            "events_per_min": 1.0,
            "verified_today": 1,
            "attention": 1,
        },
        "nodes": [
            {
                "id": node_id,
                "zone": "edge",
                "label": node_id,
                "status": "healthy",
                "load": "low",
                "activity_rate": 1.0,
                "freshness_s": 0.0,
            }
        ],
        "links": [],
        "agents": [
            {
                "id": agent_id,
                "role": agent_id,
                "state": "working",
                "activity": "observing",
                "verification": "verified",
                "provider_class": "local GPU",
                "updated_at": "2026-07-23T00:00:00+00:00",
            }
        ],
        "markets": {
            "network": "Robinhood Chain",
            "status": "offline",
            "feed_age_s": 0.0,
            "events_per_min": 0.0,
            "paper_strategies": 0,
            "decision_gate": "off",
            "execution": "off",
        },
        "events": [],
        "desk": {
            "version": 1,
            "updated_at": "2026-07-23T00:00:00+00:00",
            "posture": "unknown",
            "leader": "unknown",
            "validation": {"oos_pass": 0, "oos_total": 0, "conflicts": 0},
            "decisions": {
                "pending": 0,
                "pending_review": 0,
                "approved_awaiting_execution": 0,
                "eligible_execution": 0,
                "blocked": 0,
            },
            "execution": "unknown",
            "feeds": {"fresh": 0, "total": 0},
            "tracks": [],
        },
    }


def test_merge_keeps_mac_task_agents_and_unions_nodes_and_links():
    mac = _sample_snapshot("mac-agent", "mac-node", 100)
    win = _sample_snapshot("win-agent", "win-node", 200)
    merged = _merge_snapshots(mac, win)

    assert {a["id"] for a in merged["agents"]} == {"mac-agent"}
    assert {n["id"] for n in merged["nodes"]} == {"mac-node", "win-node"}
    assert merged["sequence"] == 201
    assert merged["summary"]["active_agents"] == 1
    assert merged["summary"]["events_per_min"] is None
    assert merged["summary"]["verified_today"] is None
    assert merged["summary"]["attention"] == 0


def test_merge_prefers_later_observation():
    mac = _sample_snapshot("mac-agent", "mac-node", 100)
    win = copy.deepcopy(mac)
    win["observed_at"] = "2026-07-23T01:00:00+00:00"
    merged = _merge_snapshots(mac, win)
    assert merged["observed_at"] == "2026-07-23T01:00:00+00:00"


def test_merge_respects_bounds():
    mac = _sample_snapshot("mac-agent", "mac-node", 100)
    win = copy.deepcopy(mac)
    win["agents"] = [dict(agent, id=f"agent-{i}") for i, agent in enumerate(win["agents"] * 40)]
    win["nodes"] = [dict(node, id=f"node-{i}") for i, node in enumerate(win["nodes"] * 30)]
    merged = _merge_snapshots(mac, win)
    assert {agent["id"] for agent in merged["agents"]} == {"mac-agent"}
    assert len(merged["nodes"]) <= 24


def test_merge_uses_windows_decision_projection():
    mac = _sample_snapshot("mac-agent", "mac-node", 100)
    win = _sample_snapshot("win-agent", "win-node", 200)
    win["desk"].update({
        "posture": "capital_preservation",
        "leader": "none",
        "execution": "halted",
        "validation": {"oos_pass": 0, "oos_total": 7, "conflicts": 1},
        "feeds": {"fresh": 7, "total": 7},
        "tracks": [{
            "strategy": "sniper",
            "status": "current",
            "live_return_pct": 176.0,
            "green_days": 1,
            "target_days": 14,
            "open_count": 0,
            "data_flags": 0,
            "freshness_s": 3.0,
        }],
        "decisions": {
            "pending": 2,
            "pending_review": 2,
            "approved_awaiting_execution": 14,
            "eligible_execution": 0,
            "blocked": 14,
        },
    })
    merged = _merge_snapshots(mac, win)
    assert merged["desk"] == win["desk"]
    assert merged["summary"]["attention"] == 2


def test_merge_does_not_count_windows_services_as_active_agents():
    mac = _sample_snapshot("mac-agent", "mac-node", 100)
    mac["summary"]["active_agents"] = 0
    win = _sample_snapshot("telegram-service", "win-node", 200)
    win["agents"][0]["state"] = "working"
    merged = _merge_snapshots(mac, win)
    assert merged["summary"]["active_agents"] == 0
    assert all(agent["id"] != "telegram-service" for agent in merged["agents"])


def test_merge_omits_unobserved_windows_desk_instead_of_publishing_null_counts():
    mac = _sample_snapshot("mac-agent", "mac-node", 100)
    mac.pop("desk")
    win = _sample_snapshot("win-agent", "win-node", 200)
    win["desk"] = {
        "version": 1,
        "updated_at": None,
        "posture": "unknown",
        "leader": "unknown",
        "validation": {"oos_pass": None, "oos_total": None, "conflicts": None},
        "decisions": {"pending": None},
        "execution": "unknown",
        "feeds": {"fresh": None, "total": None},
        "tracks": [],
    }

    merged = _merge_snapshots(mac, win)

    assert "desk" not in merged
    validated = validate_snapshot(merged)
    assert validated["desk"]["posture"] == "unknown"


def _write_conjecture(path: Path, *, observed_at: datetime) -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "utc": observed_at.isoformat().replace("+00:00", "Z"),
                "primary_focus": "ari_portfolio",
                "account": {"balance": 9_999_999},
                "raw_prompt": "private deliberation that must never be projected",
                "opinions": [
                    {
                        "id": "btc_bear_bottomed",
                        "claim": "Bitcoin has put in the corrective-phase low.",
                        "p": 0.524,
                        "stance": "uncertain",
                        "resolution_days": 90,
                        "confidence": "low",
                        "falsifier": "A fresh cycle low would falsify this view.",
                        "positions": [{"instrument": "private", "size": 123}],
                    },
                    {
                        "claim": "A second opinion must not enter the public projection.",
                        "p": 0.99,
                        "stance": "lean_yes",
                        "resolution_days": 365,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_research_projection_maps_only_the_first_allowlisted_thesis(tmp_path: Path):
    now = datetime(2026, 7, 31, 19, 0, tzinfo=UTC)
    candidate = tmp_path / "latest.json"
    _write_conjecture(candidate, observed_at=now - timedelta(minutes=1))

    projection = _load_research_projection(candidate, now=now.timestamp())

    assert projection == {
        "observed_at": "2026-07-31T18:59:00+00:00",
        "thesis": {
            "claim": "Bitcoin has put in the corrective-phase low.",
            "stance": "uncertain",
            "probability": 0.524,
            "horizon_days": 90,
        },
    }
    encoded = json.dumps(projection)
    for private_value in (
        "account",
        "balance",
        "raw_prompt",
        "positions",
        "instrument",
        "falsifier",
        "confidence",
        "second opinion",
    ):
        assert private_value not in encoded


def test_research_projection_fails_closed_when_stale_or_sensitive(tmp_path: Path):
    now = datetime(2026, 7, 31, 19, 0, tzinfo=UTC)
    stale = tmp_path / "stale.json"
    _write_conjecture(stale, observed_at=now - timedelta(hours=24, seconds=1))
    assert _load_research_projection(stale, now=now.timestamp()) is None

    sensitive = tmp_path / "sensitive.json"
    _write_conjecture(sensitive, observed_at=now - timedelta(minutes=1))
    document = json.loads(sensitive.read_text(encoding="utf-8"))
    document["opinions"][0]["claim"] = "Read /Users/aribs/private/account.json"
    sensitive.write_text(json.dumps(document), encoding="utf-8")
    assert _load_research_projection(sensitive, now=now.timestamp()) == {
        "observed_at": "2026-07-31T18:59:00+00:00",
        "thesis": {
            "claim": "Bitcoin has put in the cycle low for this bear/corrective phase",
            "stance": "uncertain",
            "probability": 0.524,
            "horizon_days": 90,
        },
    }


def test_research_projection_omits_unknown_id_and_freeform_stance(tmp_path: Path):
    now = datetime(2026, 7, 31, 19, 0, tzinfo=UTC)
    candidate = tmp_path / "latest.json"
    _write_conjecture(candidate, observed_at=now - timedelta(minutes=1))
    document = json.loads(candidate.read_text(encoding="utf-8"))
    document["opinions"][0]["id"] = "private_freeform_opinion"
    candidate.write_text(json.dumps(document), encoding="utf-8")
    assert _load_research_projection(candidate, now=now.timestamp()) is None

    document["opinions"][0]["id"] = "btc_bear_bottomed"
    document["opinions"][0]["stance"] = "Ari holds this view privately"
    candidate.write_text(json.dumps(document), encoding="utf-8")
    assert _load_research_projection(candidate, now=now.timestamp()) is None


def test_merge_carries_the_allowlisted_research_projection():
    mac = _sample_snapshot("mac-agent", "mac-node", 100)
    win = _sample_snapshot("win-agent", "win-node", 200)
    research = {
        "observed_at": "2026-07-23T00:00:00+00:00",
        "thesis": {
            "claim": "A bounded public thesis.",
            "stance": "uncertain",
            "probability": 0.524,
            "horizon_days": 90,
        },
    }

    merged = _merge_snapshots(mac, win, research=research)

    assert merged["research"] == research
    assert validate_snapshot(merged)["research"] == research

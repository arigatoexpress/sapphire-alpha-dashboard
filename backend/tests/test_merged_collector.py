"""Tests for the Mac + Windows merged telemetry collector."""

from __future__ import annotations

import copy
import json

from telemetry.merged_collector import _merge_snapshots


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


def test_merge_unions_agents_nodes_and_links():
    mac = _sample_snapshot("mac-agent", "mac-node", 100)
    win = _sample_snapshot("win-agent", "win-node", 200)
    merged = _merge_snapshots(mac, win)

    assert {a["id"] for a in merged["agents"]} == {"mac-agent", "win-agent"}
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
    assert len(merged["agents"]) <= 32
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

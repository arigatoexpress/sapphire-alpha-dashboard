r"""Windows workhorse telemetry publisher for Sapphire Alpha Dashboard.

Collects agent-worker heartbeat, Ollama ps, GPU status, and persisted desk state
from a Windows node and pushes a schema-v1 signed telemetry snapshot to:
    https://sapphirealpha.xyz/api/v1/telemetry

Environment:
    TELEMETRY_INGEST_SECRET          required for --push
    SAPPHIRE_TELEMETRY_ENDPOINT      defaults to https://sapphirealpha.xyz/api/v1/telemetry
    AGENT_WORKER_DIR                 defaults to %USERPROFILE%\agent-worker
    DESK_STATE_DIR                   defaults to %USERPROFILE%\.sapphire\desk
    OLLAMA_URL                       defaults to http://127.0.0.1:11434

Run on Windows (one-shot):
    python C:\Users\aribs\.sapphire\win_collector.py --push

Run from Mac via SSH:
    source ~/.sapphire/sapphirealpha-telemetry.env
    ssh win "set TELEMETRY_INGEST_SECRET=$TELEMETRY_INGEST_SECRET && python C:\Users\aribs\.sapphire\win_collector.py --push"

No secrets, wallet material, hostnames, paths, or IP addresses are included in
the transmitted snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_ENDPOINT = "https://sapphirealpha.xyz/api/v1/telemetry"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"

# Semantic limits mirror backend.live_telemetry validators.
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_PUBLIC_STRATEGIES = {
    "flow-follow", "sniper", "equity", "rotation",
    "mean-rev", "smart-money", "breakout",
}

# This file is deployed standalone to the Windows box and run there over SSH, so
# it cannot import telemetry/probes.py. The few measurement helpers it needs are
# duplicated below rather than adding a second file that must be copied in step
# with this one — a missing import on that host means no Windows snapshot at all.
# The rules are the same ones probes.py states: a number is a measurement, None
# means not measured, an append-only source with an empty window measured zero.
MEASUREMENT_WINDOW_SECONDS = 300.0


def _now() -> float:
    return time.time()


def _ts_iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(_now() if ts is None else ts, UTC).isoformat()


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _nonnegative_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _count_text(value: int | None, noun: str) -> str:
    if value is None:
        return f"{noun} count not observed"
    suffix = "" if value == 1 else "s"
    return f"{value} {noun}{suffix}"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _unknown_desk() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "posture": "unknown",
        "leader": "unknown",
        "validation": {"oos_pass": None, "oos_total": None, "conflicts": None},
        "decisions": {
            "pending": None,
            "pending_review": None,
            "approved_awaiting_execution": None,
            "eligible_execution": None,
            "blocked": None,
            "pending_policy_blocked": None,
        },
        "execution": "unknown",
        "feeds": {"fresh": None, "total": None},
        "tracks": [],
        "risk": {
            "ledger_state": "unknown",
            "realized_drawdown_pct": None,
            "drawdown_limit_pct": None,
            "budget_remaining_pct": None,
            "new_risk": "unknown",
        },
        "experiment": {
            "status": "unknown",
            "qualified_days": None,
            "required_days": None,
            "last_committed_date": None,
            "collector": "unknown",
        },
        "epistemics": {
            "updated_ts": None,
            "fresh": False,
            "thesis": None,
            "regime": {
                "label": "unknown", "fit": None, "data_quality": None, "drivers": [],
            },
            "falsifiers": [],
            "learning": {
                "status": "unavailable", "open": None, "resolved": None,
                "mean_brier": None, "accuracy": None, "lessons": 0,
                "updated_ts": None,
            },
        },
        "autonomy": {
            "desired": "off", "active": False,
            "new_entries": "waiting", "reason": "not observed",
        },
        "safety_floor": {
            "gate_valid": False, "pause_clear": None,
            "ledger": "unknown", "bounded_policy": False,
        },
    }


def _desk_projection(path: Path) -> dict[str, Any]:
    """Read only a bounded persisted desk observation."""
    value = _read_json(path)
    try:
        required = {
            "version", "updated_at", "posture", "leader", "validation",
            "decisions", "execution", "feeds",
        }
        if not required <= set(value) or not set(value) <= required | {
            "risk", "experiment", "tracks",
            "epistemics", "autonomy", "safety_floor",
        }:
            return _unknown_desk()
        validation = value["validation"]
        decisions = value["decisions"]
        feeds = value["feeds"]
        epistemics = value.get("epistemics")
        autonomy = value.get("autonomy")
        safety_floor = value.get("safety_floor")
        if (
            value["version"] != 1
            or value["posture"] not in {
                "capital_preservation", "selective_risk", "risk_seeking", "neutral"
            }
            or value["leader"] not in {"credible", "none"}
            or value["execution"] not in {"halted", "off", "gated"}
            or not {"oos_pass", "oos_total", "conflicts"} <= set(validation)
            or not set(validation) <= {
                "oos_pass", "oos_total", "conflicts", "conflict_details",
                "replay_span_hours", "replay_data_through",
            }
            or "pending" not in decisions
            or not set(decisions).issubset({
                "pending",
                "pending_review",
                "approved_awaiting_execution",
                "eligible_execution",
                "blocked",
                "pending_policy_blocked",
            })
            or set(feeds) != {"fresh", "total"}
            or (
                epistemics is not None
                and (
                    not isinstance(epistemics, dict)
                    or not set(epistemics) <= {
                        "updated_ts", "fresh", "thesis", "regime",
                        "falsifiers", "learning",
                    }
                    or len(json.dumps(epistemics)) > 20_000
                )
            )
            or (
                autonomy is not None
                and (
                    not isinstance(autonomy, dict)
                    or set(autonomy) != {
                        "desired", "active", "new_entries", "reason",
                    }
                    or autonomy.get("desired") not in {"on", "off"}
                    or not isinstance(autonomy.get("active"), bool)
                    or autonomy.get("new_entries") not in {"available", "waiting"}
                    or not isinstance(autonomy.get("reason"), str)
                    or len(autonomy["reason"]) > 160
                )
            )
            or (
                safety_floor is not None
                and (
                    not isinstance(safety_floor, dict)
                    or set(safety_floor) != {
                        "gate_valid", "pause_clear", "ledger", "bounded_policy",
                    }
                    or not isinstance(safety_floor.get("gate_valid"), bool)
                    or (
                        safety_floor.get("pause_clear") is not None
                        and not isinstance(safety_floor.get("pause_clear"), bool)
                    )
                    or safety_floor.get("ledger") not in {"reconciled", "unknown"}
                    or not isinstance(safety_floor.get("bounded_policy"), bool)
                )
            )
        ):
            return _unknown_desk()
        counts = [
            validation["oos_pass"], validation["oos_total"], validation["conflicts"],
            feeds["fresh"], feeds["total"],
        ]
        if any(
            isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 1_000
            for count in counts
        ):
            return _unknown_desk()
        if validation["oos_pass"] > validation["oos_total"] or feeds["fresh"] > feeds["total"]:
            return _unknown_desk()
        conflict_details = validation.get("conflict_details", [])
        replay_span_hours = validation.get("replay_span_hours")
        replay_data_through = validation.get("replay_data_through")
        if (
            not isinstance(conflict_details, list)
            or len(conflict_details) > 7
            or (
                "conflict_details" in validation
                and len(conflict_details) != validation["conflicts"]
            )
            or replay_span_hours is not None
            and (
                isinstance(replay_span_hours, bool)
                or not isinstance(replay_span_hours, (int, float))
                or not math.isfinite(float(replay_span_hours))
                or not 0 <= float(replay_span_hours) <= 100_000
            )
        ):
            return _unknown_desk()
        seen_strategies = set()
        normalized_conflicts = []
        for index, conflict in enumerate(conflict_details):
            if not isinstance(conflict, dict) or set(conflict) != {
                "strategy", "live_return_pct", "replay_return_pct", "gap_pp",
            }:
                return _unknown_desk()
            strategy = conflict["strategy"]
            values = (
                conflict["live_return_pct"],
                conflict["replay_return_pct"],
                conflict["gap_pp"],
            )
            if (
                strategy not in _PUBLIC_STRATEGIES
                or strategy in seen_strategies
                or any(
                    isinstance(item, bool)
                    or not isinstance(item, (int, float))
                    or not math.isfinite(float(item))
                    for item in values
                )
                or not -1_000 <= float(values[0]) <= 10_000
                or not -1_000 <= float(values[1]) <= 10_000
                or not 0 <= float(values[2]) <= 10_000
            ):
                return _unknown_desk()
            seen_strategies.add(strategy)
            normalized_conflicts.append(dict(conflict))
        if replay_data_through is not None:
            if not isinstance(replay_data_through, str):
                return _unknown_desk()
            try:
                if (
                    datetime.fromisoformat(replay_data_through).date().isoformat()
                    != replay_data_through
                ):
                    return _unknown_desk()
            except ValueError:
                return _unknown_desk()
        tracks_raw = value.get("tracks", [])
        if not isinstance(tracks_raw, list) or len(tracks_raw) > 7:
            return _unknown_desk()
        normalized_tracks = []
        seen_tracks = set()
        for track in tracks_raw:
            if not isinstance(track, dict) or set(track) != {
                "strategy", "status", "live_return_pct", "green_days",
                "target_days", "open_count", "data_flags", "freshness_s",
            }:
                return _unknown_desk()
            strategy = track["strategy"]
            status = track["status"]
            numeric = (
                track["live_return_pct"],
                track["green_days"],
                track["target_days"],
                track["open_count"],
                track["data_flags"],
                track["freshness_s"],
            )
            if (
                strategy not in _PUBLIC_STRATEGIES
                or strategy in seen_tracks
                or status not in {"current", "stale", "inactive"}
                or any(
                    isinstance(item, bool)
                    or not isinstance(item, (int, float))
                    or not math.isfinite(float(item))
                    for item in numeric
                )
                or any(
                    isinstance(track[field], bool)
                    or not isinstance(track[field], int)
                    for field in (
                        "green_days", "target_days", "open_count", "data_flags",
                    )
                )
                or not -1_000 <= float(track["live_return_pct"]) <= 10_000
                or not 0 <= track["green_days"] <= track["target_days"] <= 100
                or not 0 <= track["open_count"] <= 1_000
                or not 0 <= track["data_flags"] <= 1_000
                or not 0 <= float(track["freshness_s"]) <= 31_536_000
            ):
                return _unknown_desk()
            seen_tracks.add(strategy)
            normalized_tracks.append(dict(track))
        decision_counts = {
            "pending": decisions["pending"],
            "pending_review": decisions.get("pending_review"),
            "approved_awaiting_execution": decisions.get("approved_awaiting_execution"),
            "eligible_execution": decisions.get("eligible_execution"),
            "blocked": decisions.get("blocked"),
            "pending_policy_blocked": decisions.get("pending_policy_blocked"),
        }
        if any(
            count is not None
            and (
                isinstance(count, bool)
                or not isinstance(count, int)
                or not 0 <= count <= 1_000
            )
            for count in decision_counts.values()
        ):
            return _unknown_desk()
        if (
            decision_counts["pending_review"] is not None
            and decision_counts["pending_policy_blocked"] is not None
            and decision_counts["pending"] != (
                decision_counts["pending_review"]
                + decision_counts["pending_policy_blocked"]
            )
        ):
            return _unknown_desk()
        if all(
            decision_counts[key] is not None
            for key in (
                "approved_awaiting_execution",
                "eligible_execution",
                "blocked",
            )
        ) and (
            decision_counts["eligible_execution"] + decision_counts["blocked"]
            != decision_counts["approved_awaiting_execution"]
        ):
            return _unknown_desk()
        risk = value.get("risk") or {
            "ledger_state": "unknown",
            "realized_drawdown_pct": None,
            "drawdown_limit_pct": None,
            "budget_remaining_pct": None,
            "new_risk": "unknown",
        }
        if set(risk) != {
            "ledger_state", "realized_drawdown_pct", "drawdown_limit_pct",
            "budget_remaining_pct", "new_risk",
        }:
            return _unknown_desk()
        risk_values = [
            risk["realized_drawdown_pct"],
            risk["drawdown_limit_pct"],
            risk["budget_remaining_pct"],
        ]
        if (
            risk["ledger_state"] not in {"reconciled", "unknown"}
            or risk["new_risk"] not in {"available", "restricted", "blocked", "unknown"}
            or any(
                item is not None
                and (
                    isinstance(item, bool)
                    or not isinstance(item, (int, float))
                    or not 0 <= item <= 100
                )
                for item in risk_values
            )
            or (
                risk["ledger_state"] == "reconciled"
                and (
                    any(item is None for item in risk_values)
                    or risk["new_risk"] == "unknown"
                )
            )
            or (
                risk["ledger_state"] == "unknown"
                and (
                    any(item is not None for item in risk_values)
                    or risk["new_risk"] != "unknown"
                )
            )
        ):
            return _unknown_desk()
        experiment = value.get("experiment") or {
            "status": "unknown",
            "qualified_days": None,
            "required_days": None,
            "last_committed_date": None,
            "collector": "unknown",
        }
        if set(experiment) != {
            "status", "qualified_days", "required_days",
            "last_committed_date", "collector",
        }:
            return _unknown_desk()
        experiment_states = {
            "collecting", "ready_for_terminal_evaluation", "complete",
            "invalidated", "unknown",
        }
        qualified = experiment["qualified_days"]
        required_days = experiment["required_days"]
        if (
            experiment["status"] not in experiment_states
            or experiment["collector"] not in {"current", "stale", "missing", "unknown"}
            or any(
                item is not None
                and (
                    isinstance(item, bool)
                    or not isinstance(item, int)
                    or not 0 <= item <= 100
                )
                for item in (qualified, required_days)
            )
            or (
                experiment["status"] == "unknown"
                and (
                    qualified is not None
                    or required_days is not None
                    or experiment["last_committed_date"] is not None
                    or experiment["collector"] != "unknown"
                )
            )
            or (
                experiment["status"] != "unknown"
                and (
                    qualified is None
                    or required_days is None
                    or qualified > required_days
                )
            )
        ):
            return _unknown_desk()
        committed_date = experiment["last_committed_date"]
        if committed_date is not None:
            if not isinstance(committed_date, str):
                return _unknown_desk()
            try:
                if datetime.fromisoformat(committed_date).date().isoformat() != committed_date:
                    return _unknown_desk()
            except ValueError:
                return _unknown_desk()
        datetime.fromisoformat(str(value["updated_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return _unknown_desk()
    projected_validation = {
        "oos_pass": validation["oos_pass"],
        "oos_total": validation["oos_total"],
        "conflicts": validation["conflicts"],
    }
    if "conflict_details" in validation:
        projected_validation.update({
            "conflict_details": normalized_conflicts,
            "replay_span_hours": (
                None if replay_span_hours is None else float(replay_span_hours)
            ),
            "replay_data_through": replay_data_through,
        })
    result = {
        "version": 1,
        "updated_at": value["updated_at"],
        "posture": value["posture"],
        "leader": value["leader"],
        "validation": projected_validation,
        "decisions": decision_counts,
        "execution": value["execution"],
        "feeds": dict(feeds),
        "tracks": normalized_tracks,
        "risk": dict(risk),
        "experiment": dict(experiment),
    }
    if isinstance(epistemics, dict):
        result["epistemics"] = json.loads(json.dumps(epistemics))
    if isinstance(autonomy, dict):
        result["autonomy"] = dict(autonomy)
    if isinstance(safety_floor, dict):
        result["safety_floor"] = dict(safety_floor)
    return result


def _directory_rate_per_min(
    path: Path,
    *,
    now: float,
    window_s: float = MEASUREMENT_WINDOW_SECONDS,
) -> float | None:
    """Files that landed in a drop directory inside the window, per minute."""
    try:
        entries = list(path.iterdir())
    except OSError:
        return None
    floor = now - window_s
    observed = 0
    for entry in entries:
        try:
            modified = entry.stat().st_mtime
        except OSError:
            continue
        if floor <= modified <= now:
            observed += 1
    return round(observed / (window_s / 60.0), 3)


def _ollama_ps(base: str) -> dict[str, Any]:
    """Query Ollama and time the call.

    `latency_ms` here is the real round trip the agent worker pays on every
    inference request — same host, same socket, same server — so it is the
    honest latency for the worker -> inference edge. None when the call failed,
    because an unreachable server has no latency, it has an outage.
    """
    out: dict[str, Any] = {"ok": False, "latency_ms": None}
    started = time.perf_counter()
    try:
        req = urllib.request.Request(f"{base}/api/ps", headers={"User-Agent": "sapphire-win-telemetry/1"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        out["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        out["ok"] = True
        models = data.get("models")
        if isinstance(models, list):
            out["models"] = models
            out["loaded_count"] = len(models)
            sizes = [
                _nonnegative_int(model.get("size_vram"))
                for model in models
                if isinstance(model, dict)
            ]
            out["vram_bytes"] = (
                sum(size for size in sizes if size is not None)
                if len(sizes) == len(models) and all(size is not None for size in sizes)
                else None
            )
    except Exception as e:
        out["error"] = str(e)[:80]
    return out


def _ollama_tags(base: str) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "count": None}
    try:
        req = urllib.request.Request(f"{base}/api/tags", headers={"User-Agent": "sapphire-win-telemetry/1"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        models = data.get("models")
        if isinstance(models, list):
            out["ok"] = True
            out["count"] = len(models)
    except Exception as e:
        out["error"] = str(e)[:80]
    return out


def _nvidia_smi() -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False}
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,name",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            out["error"] = (result.stderr or "nvidia-smi failed")[:80]
            return out
        line = result.stdout.strip().splitlines()[0]
        # "0 %, 8 %, 15344 MiB, 16303 MiB, 25, NVIDIA GeForce RTX 5070 Ti"
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            out["error"] = "unexpected nvidia-smi format"
            return out
        out["ok"] = True
        out["gpu_util_pct"] = float(parts[0].replace("%", "").strip())
        out["mem_util_pct"] = float(parts[1].replace("%", "").strip())
        out["mem_used_mib"] = float(parts[2].replace("MiB", "").strip())
        out["mem_total_mib"] = float(parts[3].replace("MiB", "").strip())
        out["temp_c"] = float(parts[4].strip())
        out["name"] = parts[5]
    except FileNotFoundError:
        out["error"] = "nvidia-smi not found"
    except Exception as e:
        out["error"] = str(e)[:80]
    return out


def _disk_free_gb(path: str = "C:\\") -> float | None:
    try:
        usage = shutil.disk_usage(path)
        return round(usage.free / (1024**3), 1)
    except Exception:
        return None


def _pause_observation(home: Path) -> tuple[str, str | None]:
    """Read the durable pause sentinel; absence is not evidence of clear."""
    path = home / ".sapphire" / "autonomous_trading_pause"
    if not path.exists():
        return "unknown", None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return "unknown", None
        observed = raw.get("observed_at") or raw.get("created_at")
        if not isinstance(observed, str) or not observed:
            observed = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
        datetime.fromisoformat(observed.replace("Z", "+00:00"))
        return "active", observed
    except (OSError, ValueError, json.JSONDecodeError):
        return "unknown", None


def _agent_id(label: str, index: int) -> str:
    slug = "".join(char if char.isalnum() else "-" for char in label.lower()).strip("-")
    slug = "-".join(filter(None, slug.split("-")))[:32]
    return slug or f"observer-{index + 1}"


def _agent(role: str, state: str, activity: str, verification: str, provider: str, updated_at: str, index: int) -> dict[str, Any]:
    return {
        "id": _agent_id(role, index),
        "role": role[:64],
        "state": state,
        "activity": activity[:120],
        "verification": verification,
        "provider_class": provider,
        "updated_at": updated_at,
    }


def build_snapshot(
    home: Path,
    *,
    agent_worker_dir: Path | None = None,
    desk_state_dir: Path | None = None,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    now: float | None = None,
) -> dict[str, Any]:
    """Build a schema-v1 telemetry snapshot from Windows-local sources."""
    now = _now() if now is None else now
    observed_at = _ts_iso(now)

    agent_worker_dir = agent_worker_dir or home / "agent-worker"
    desk_state_dir = desk_state_dir or home / ".sapphire" / "desk"

    hb = _read_json(agent_worker_dir / "heartbeat.json")
    metrics = _read_json(agent_worker_dir / "metrics.json")
    ps = _ollama_ps(ollama_url)
    tags = _ollama_tags(ollama_url)
    gpu = _nvidia_smi()
    disk_free = _disk_free_gb()
    pause_state, pause_observed_at = _pause_observation(home)
    desk = _desk_projection(desk_state_dir / "desk-summary.json")
    desk.setdefault("safety_floor", _unknown_desk()["safety_floor"])
    desk["safety_floor"]["pause_clear"] = (
        False if pause_state == "active" else None
    )

    # Heartbeat freshness
    hb_ts = hb.get("ts") or metrics.get("last_sweep")
    if isinstance(hb_ts, str):
        try:
            # heartbeat.json timestamps are written in Windows local time.
            hb_age_s = now - time.mktime(time.strptime(hb_ts, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            hb_age_s = 86_400.0
    else:
        hb_age_s = 86_400.0
    hb_age_s = max(0.0, hb_age_s)
    hb_state = str(hb.get("state") or "unknown").lower()

    # Ollama freshness
    ollama_age_s = 0.0 if ps["ok"] else 86_400.0

    # GPU health
    gpu_healthy = gpu.get("ok") and gpu.get("gpu_util_pct") is not None

    # Workhorse overall health
    workhorse_status = "healthy"
    if not ps["ok"] or not gpu_healthy or (disk_free is not None and disk_free < 10.0):
        workhorse_status = "degraded"
    if not ps["ok"] and not gpu_healthy:
        workhorse_status = "down"

    # Agent-worker health
    if hb_age_s <= 300 and hb_state in {"idle", "working"}:
        worker_status = "healthy"
        worker_state = "working" if hb_state == "working" else "idle"
    elif hb_age_s <= 900:
        worker_status = "degraded"
        worker_state = "idle"
    else:
        worker_status = "down"
        worker_state = "offline"

    # Ollama inference health
    ollama_status = "healthy" if ps["ok"] else "down"

    # Knowledge archive health (driven by worker metrics)
    archive_status = worker_status

    # Counts remain unknown when their source did not supply them. The previous
    # implementation coerced all missing values to zero, then multiplied them
    # into plausible-looking activity rates and load levels.
    loaded_models = _nonnegative_int(ps.get("loaded_count"))
    available_models = _nonnegative_int(tags.get("count"))
    tasks_total = _nonnegative_int(metrics.get("tasks"))
    pass_count = _nonnegative_int(metrics.get("pass"))
    fail_count = _nonnegative_int(metrics.get("fail"))
    gpu_util_pct = _nonnegative_number(gpu.get("gpu_util_pct"))
    mem_util_pct = _nonnegative_number(gpu.get("mem_util_pct"))
    temp_c = _nonnegative_number(gpu.get("temp_c"))

    # Link measurements. Every value below was observed; every None means the
    # path has no observable on this host, and none of them are filled in with a
    # stand-in. The old link block published `pending * 4`, `loaded_models * 8`,
    # `gpu_util * 1.5` and a cumulative task counter as events per minute.
    worker_intake_rate = _directory_rate_per_min(
        agent_worker_dir / "queue",
        now=now,
    )
    archive_completion_rate = _directory_rate_per_min(agent_worker_dir / "done", now=now)
    inference_latency_ms = ps.get("latency_ms")
    worker_provider = (
        "local GPU"
        if gpu_healthy and (
            "gpu" in str(hb.get("model", "")).lower()
            or (_nonnegative_int(ps.get("vram_bytes")) or 0) > 0
        )
        else "local CPU"
    )

    nodes = [
        {
            "id": "win-workhorse",
            "zone": "compute",
            "label": "Windows workhorse",
            "status": workhorse_status,
            "load_band": "high" if gpu_util_pct is not None and gpu_util_pct >= 80 else "medium" if gpu_util_pct is not None and gpu_util_pct > 0 else "idle",
            "activity_rate": None,
            "freshness_s": round(min(ollama_age_s, 86_400.0), 3),
        },
        {
            "id": "agent-worker",
            "zone": "intelligence",
            "label": "Agent worker",
            "status": worker_status,
            "load_band": "medium" if worker_state == "working" else "idle",
            "activity_rate": worker_intake_rate,
            "freshness_s": round(min(hb_age_s, 86_400.0), 3),
        },
        {
            "id": "ollama-inference",
            "zone": "compute",
            "label": "Ollama inference",
            "status": ollama_status,
            "load_band": "high" if loaded_models is not None and loaded_models >= 3 else "medium" if loaded_models is not None and loaded_models >= 1 else "idle",
            "activity_rate": None,
            "freshness_s": round(min(ollama_age_s, 86_400.0), 3),
        },
        {
            "id": "knowledge-archive",
            "zone": "archive",
            "label": "Knowledge archive",
            "status": archive_status,
            "load_band": "medium" if archive_completion_rate is not None and archive_completion_rate > 0 else "idle",
            "activity_rate": archive_completion_rate,
            "freshness_s": round(min(hb_age_s, 86_400.0), 3),
        },
    ]

    links = [
        # Measured round trip to the inference server. Ollama's request log is
        # empty on this host, so its request rate is genuinely unobservable.
        {"source": "agent-worker", "target": "ollama-inference", "status": ollama_status, "latency_ms": inference_latency_ms, "event_rate": None, "signal_class": "agent"},
        # Nothing observable either way: the GPU exposes utilisation and memory,
        # neither of which is a latency or a rate. Utilisation reaches the site
        # through the win-workhorse node, where it belongs.
        {"source": "ollama-inference", "target": "win-workhorse", "status": workhorse_status, "latency_ms": None, "event_rate": None, "signal_class": "network"},
        # Completed task files landing in the worker's done directory, per minute.
        {"source": "agent-worker", "target": "knowledge-archive", "status": archive_status, "latency_ms": None, "event_rate": archive_completion_rate, "signal_class": "archive"},
    ]

    agents = [
        _agent(
            role="Agent worker",
            state=worker_state,
            activity=(
                f"{worker_state} now | lifetime: {tasks_total} total, "
                f"{pass_count} completed, {fail_count} failed"
                if None not in (tasks_total, pass_count, fail_count)
                else " | ".join((
                    f"{worker_state} now",
                    _count_text(tasks_total, "lifetime task"),
                    _count_text(pass_count, "completed task"),
                    _count_text(fail_count, "failed task"),
                ))
            ),
            verification="verified" if worker_status == "healthy" else "pending" if worker_status == "degraded" else "failed",
            provider=worker_provider,
            updated_at=_ts_iso(now - hb_age_s),
            index=0,
        ),
        _agent(
            role="Ollama inference host",
            state="working" if ps["ok"] else "offline",
            activity=f"{_count_text(loaded_models, 'loaded model')} | {_count_text(available_models, 'available model')}",
            verification="verified" if ps["ok"] else "failed",
            provider="local GPU",
            updated_at=observed_at,
            index=1,
        ),
        _agent(
            role="GPU workhorse",
            state="working" if gpu_healthy else "offline",
            activity=" | ".join(
                (
                    "GPU utilization not observed"
                    if gpu_util_pct is None
                    else f"GPU utilization {gpu_util_pct:g}%",
                    "memory utilization not observed"
                    if mem_util_pct is None
                    else f"memory utilization {mem_util_pct:g}%",
                    "temperature not observed"
                    if temp_c is None
                    else f"temperature {temp_c:g}C",
                )
            ),
            verification="verified" if gpu_healthy else "failed",
            provider="local GPU",
            updated_at=observed_at,
            index=2,
        ),
    ]

    events: list[dict[str, Any]] = []
    if ps["ok"]:
        events.append({
            "id": f"win-ollama-{int(now)}",
            "observed_at": observed_at,
            "event_class": "agent",
            "source": "compute",
            "target": "compute",
            "label": (
                "Ollama model count not observed"
                if loaded_models is None
                else f"Ollama serving {loaded_models} model(s)"
            ),
            "status": "verified",
        })
    if worker_status != "down":
        events.append({
            "id": f"win-worker-{int(now)}",
            "observed_at": _ts_iso(now - hb_age_s),
            "event_class": "agent",
            "source": "intelligence",
            "target": "archive",
            "label": f"Agent worker {hb_state}",
            "status": "verified" if worker_status == "healthy" else "degraded",
        })
    if gpu_healthy:
        events.append({
            "id": f"win-gpu-{int(now)}",
            "observed_at": observed_at,
            "event_class": "agent",
            "source": "compute",
            "target": "compute",
            "label": "GPU state observed",
            "status": "verified",
        })
    if pause_state == "active":
        events.append({
            "id": f"win-pause-{int(now)}",
            "observed_at": pause_observed_at,
            "event_class": "reliability",
            "source": "compute",
            "target": "compute",
            "label": "Autonomous trading pause sentinel present",
            "status": "verified",
        })

    degraded = any(node["status"] in {"degraded", "down"} for node in nodes)
    active_agents = sum(1 for agent in agents if agent["state"] in {"working", "verifying"})

    return {
        "version": 1,
        "observed_at": observed_at,
        "sequence": time.time_ns(),
        "summary": {
            "state": "degraded" if degraded else "observing",
            "active_agents": active_agents,
            "events_per_min": None,
            "verified_today": None,
            # The public narrator's "waiting on you" sentence must use the
            # same authoritative review queue as the decision cockpit.
            "attention": desk["decisions"]["pending_review"],
        },
        "nodes": nodes,
        "links": links,
        "agents": agents,
        "markets": {
            "network": "Windows workhorse",
            "status": "offline",
            "feed_age_s": None,
            "events_per_min": None,
            "paper_strategies": None,
            "decision_gate": "unknown",
            "execution": "unknown",
        },
        "events": events,
        "desk": desk,
    }


def signed_headers(body: bytes, secret: str, *, timestamp: int | None = None, nonce: str | None = None) -> dict[str, str]:
    if len(secret) < 32:
        raise ValueError("TELEMETRY_INGEST_SECRET must be at least 32 characters")
    ts = str(int(time.time()) if timestamp is None else timestamp)
    nonce = nonce or secrets.token_urlsafe(18)
    message = ts.encode() + b"." + nonce.encode() + b"." + body
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Sapphire-Timestamp": ts,
        "X-Sapphire-Nonce": nonce,
        "X-Sapphire-Signature": signature,
    }


def _post(snapshot: dict[str, Any], *, endpoint: str, secret: str, timeout: float) -> dict[str, Any]:
    body = json.dumps(snapshot, separators=(",", ":"), allow_nan=False).encode()
    request = urllib.request.Request(endpoint, data=body, headers=signed_headers(body, secret), method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read())
    return result if isinstance(result, dict) else {}


def push(
    snapshot: dict[str, Any],
    *,
    endpoint: str,
    secret: str,
    timeout: float = 15.0,
    transport: Any = None,
) -> dict[str, Any]:
    """Publish one honest payload; never retry unknown measurements as zero."""
    transport = transport or _post
    return transport(snapshot, endpoint=endpoint, secret=secret, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Windows workhorse telemetry to Sapphire Alpha")
    parser.add_argument("--push", action="store_true", help="submit to SAPPHIRE_TELEMETRY_ENDPOINT")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    parser.add_argument("--validate-only", action="store_true", help="build snapshot and exit 0 if valid")
    args = parser.parse_args()

    home = Path.home()
    snapshot = build_snapshot(
        home,
        agent_worker_dir=Path(os.environ.get("AGENT_WORKER_DIR", str(home / "agent-worker"))),
        desk_state_dir=Path(
            os.environ.get("DESK_STATE_DIR", str(home / ".sapphire" / "desk"))
        ),
        ollama_url=os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL),
    )

    if args.validate_only:
        print(json.dumps(snapshot, indent=None if args.compact else 2, sort_keys=True))
        return 0

    if args.push:
        endpoint = os.environ.get("SAPPHIRE_TELEMETRY_ENDPOINT", DEFAULT_ENDPOINT).strip()
        secret = os.environ.get("TELEMETRY_INGEST_SECRET", "")
        if not endpoint:
            raise SystemExit("SAPPHIRE_TELEMETRY_ENDPOINT is required with --push")
        if not secret:
            raise SystemExit("TELEMETRY_INGEST_SECRET is required with --push")
        result = push(snapshot, endpoint=endpoint, secret=secret)
        print(json.dumps({"snapshot": snapshot, "result": result}, indent=None if args.compact else 2, sort_keys=True))
    else:
        print(json.dumps(snapshot, indent=None if args.compact else 2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

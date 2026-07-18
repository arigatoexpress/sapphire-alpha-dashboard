"""Project raw local observations into the public-safe Mission Snapshot.

Raw files are read locally and never transmitted. The output vocabulary is
deliberately semantic: roles, health, freshness, activity, and verification.
There is no actuation path in this module.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import secrets
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class Sources:
    rh_health: Path
    rh_feed: Path
    memes: Path
    paper: Path
    gpu: Path
    desk_cycle: Path
    agent_presence: Path | None = None

    @classmethod
    def defaults(cls) -> "Sources":
        ops = Path(os.getenv("SAPPHIRE_OPS_STATE", Path.home() / "ops-state"))
        chain = ops / "rh-chain"
        return cls(
            rh_health=chain / "agent-health-state.json",
            rh_feed=chain / "rh-feed-state.json",
            memes=chain / "memes-state.json",
            paper=chain / "paper-state.json",
            gpu=ops / "gpu-node-status.json",
            desk_cycle=ops / "deskos" / "last_cycle.json",
            agent_presence=ops / "agent-presence.json",
        )


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _epoch(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
            except ValueError:
                return None
    return None


def _age(now: float, *candidates: Any) -> float:
    timestamps = [parsed for value in candidates if (parsed := _epoch(value)) is not None]
    return round(max(0.0, now - max(timestamps)), 3) if timestamps else 86_400.0


def _health(value: Any, *, age_s: float) -> str:
    if age_s > 900:
        return "down"
    normalized = str(value or "unknown").lower()
    if normalized in {"healthy", "ok", "up", "live", "running", "current"}:
        return "healthy"
    if normalized in {"degraded", "warn", "warning", "partial"}:
        return "degraded"
    if normalized in {"down", "failed", "offline", "error"}:
        return "down"
    return "unknown"


def _agent_id(label: str, index: int) -> str:
    slug = "".join(char if char.isalnum() else "-" for char in label.lower()).strip("-")
    slug = "-".join(filter(None, slug.split("-")))[:32]
    return slug or f"observer-{index + 1}"


def _presence_agents(value: dict[str, Any]) -> list[dict[str, Any]]:
    raw_agents = value.get("agents") if isinstance(value.get("agents"), list) else []
    allowed_states = {"working", "verifying", "idle", "blocked", "offline"}
    allowed_verification = {"verified", "pending", "failed", "not_applicable"}
    allowed_providers = {"local GPU", "local CPU", "cloud reasoning", "hybrid", "rule-only", "unassigned"}
    agents: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_agents[:24]):
        if not isinstance(raw, dict):
            continue
        role = str(raw.get("role") or "Agent observer")[:64]
        state = str(raw.get("state") or "offline")
        verification = str(raw.get("verification") or "pending")
        provider = str(raw.get("provider_class") or "unassigned")
        updated_at = raw.get("updated_at")
        if state not in allowed_states or verification not in allowed_verification or provider not in allowed_providers or _epoch(updated_at) is None:
            continue
        agents.append(
            {
                "id": _agent_id(role, index),
                "role": role,
                "state": state,
                "activity": str(raw.get("activity") or "Agent state observed")[:120],
                "verification": verification,
                "provider_class": provider,
                "updated_at": datetime.fromtimestamp(_epoch(updated_at) or 0, UTC).isoformat(),
            }
        )
    return agents


def _presence_events(value: dict[str, Any], *, now: float) -> tuple[list[dict[str, Any]], float]:
    raw_events = value.get("events") if isinstance(value.get("events"), list) else []
    status_map = {
        "observed": "observed",
        "working": "observed",
        "healthy": "observed",
        "verified": "verified",
        "pending": "pending",
        "failed": "failed",
        "blocked": "degraded",
        "degraded": "degraded",
        "offline": "degraded",
    }
    events: list[dict[str, Any]] = []
    recent = 0
    for index, raw in enumerate(raw_events[-24:]):
        if not isinstance(raw, dict):
            continue
        occurred = _epoch(raw.get("occurred_at"))
        status = status_map.get(str(raw.get("status") or ""))
        if occurred is None or status is None:
            continue
        if 0 <= now - occurred <= 60:
            recent += 1
        events.append(
            {
                "id": f"presence-{index + 1}",
                "observed_at": datetime.fromtimestamp(occurred, UTC).isoformat(),
                "event_class": "agent",
                "source": "intelligence",
                "target": "archive",
                "label": str(raw.get("label") or "Agent activity observed")[:120],
                "status": status,
            }
        )
    return events, float(recent)


def _presence_health(agents: list[dict[str, Any]], *, source_errors: int = 0) -> str:
    states = {agent["state"] for agent in agents}
    if not states or states == {"offline"}:
        return "down"
    if source_errors or states & {"blocked", "offline"}:
        return "degraded"
    return "healthy"


def build_snapshot(
    sources: Sources,
    *,
    now: float | None = None,
    link_latencies: Mapping[str, float | None] | None = None,
) -> dict[str, Any]:
    """Build one schema-v1 snapshot using only bounded semantic fields."""
    now = time.time() if now is None else now
    link_latencies = link_latencies or {}
    observed_at = datetime.fromtimestamp(now, UTC).isoformat()
    rh_health = _read(sources.rh_health)
    feed = _read(sources.rh_feed)
    memes = _read(sources.memes)
    paper = _read(sources.paper)
    gpu = _read(sources.gpu)
    desk = _read(sources.desk_cycle)
    presence = _read(sources.agent_presence) if sources.agent_presence else {}

    rh_age = _age(now, rh_health.get("generated_ts"))
    feed_age = _age(now, feed.get("updated"), memes.get("updated"))
    gpu_age = _age(now, gpu.get("updated"), gpu.get("last_check"))
    desk_age = _age(now, desk.get("finished_at"), desk.get("started_at"))
    presence_agents = _presence_agents(presence)
    presence_events, presence_event_rate = _presence_events(presence, now=now)
    raw_agents = rh_health.get("agents") if isinstance(rh_health.get("agents"), list) else []
    agents: list[dict[str, Any]] = list(presence_agents)
    for index, raw in enumerate(raw_agents[:12]):
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or "Research observer")[:64]
        status = _health(raw.get("status"), age_s=rh_age)
        issue_count = len(raw.get("issues", [])) if isinstance(raw.get("issues"), list) else 0
        if any(agent["role"] == label for agent in agents):
            continue
        agents.append(
            {
                "id": _agent_id(label, index),
                "role": label,
                "state": "working" if status == "healthy" else "blocked" if status == "degraded" else "offline",
                "activity": "Observing live research signals" if status == "healthy" else f"Awaiting recovery from {issue_count} check",
                "verification": "verified" if status == "healthy" else "failed" if status == "down" else "pending",
                "provider_class": "local CPU",
                "updated_at": datetime.fromtimestamp(max(0, now - rh_age), UTC).isoformat(),
            }
        )

    service_count = sum(1 for value in (gpu.get("services") or {}).values() if bool(value)) if isinstance(gpu.get("services"), dict) else 0
    gpu_status = _health(gpu.get("status"), age_s=gpu_age)
    if gpu:
        agents.append(
            {
                "id": "gpu-workhorse",
                "role": "GPU workhorse",
                "state": "working" if gpu_status == "healthy" and service_count else "offline",
                "activity": f"Serving {service_count} compute lanes" if service_count else "Compute lanes not observed",
                "verification": "verified" if gpu_status == "healthy" else "pending",
                "provider_class": "local GPU",
                "updated_at": datetime.fromtimestamp(max(0, now - gpu_age), UTC).isoformat(),
            }
        )

    msg_rate = float(feed.get("msgs_per_min") or 0)
    inserted = int((desk.get("totals") or {}).get("inserted") or 0) if isinstance(desk.get("totals"), dict) else 0
    market_status = "current" if feed_age <= 60 else "delayed" if feed_age <= 300 else "stale" if feed else "offline"
    market_health = "healthy" if market_status == "current" else "degraded" if market_status in {"delayed", "stale"} else "down"
    source_errors = presence.get("source_errors") if isinstance(presence.get("source_errors"), int) else 0
    rh_status = _presence_health(presence_agents, source_errors=source_errors) if presence_agents else _health(rh_health.get("overall"), age_s=rh_age)
    intelligence_age = _age(now, *(agent["updated_at"] for agent in presence_agents)) if presence_agents else rh_age
    agent_rate = presence_event_rate if presence_agents else float(len(agents) * 4)
    desk_status = _health(desk.get("status"), age_s=desk_age)

    nodes = [
        {"id": "public-edge", "zone": "edge", "label": "Public edge", "status": "healthy", "load_band": "low", "activity_rate": max(1.0, msg_rate / 20), "freshness_s": 0.0},
        {"id": "orchestration", "zone": "orchestration", "label": "Orchestration", "status": desk_status, "load_band": "medium" if inserted else "idle", "activity_rate": min(120.0, inserted / 5), "freshness_s": desk_age},
        {"id": "gpu-compute", "zone": "compute", "label": "GPU compute", "status": gpu_status, "load_band": "medium" if service_count else "idle", "activity_rate": service_count * 8.0, "freshness_s": gpu_age},
        {"id": "intelligence", "zone": "intelligence", "label": "Agent intelligence", "status": rh_status, "load_band": "high" if agent_rate >= 60 else "medium" if agent_rate else "idle", "activity_rate": agent_rate, "freshness_s": intelligence_age},
        {"id": "markets", "zone": "markets", "label": "Robinhood Chain", "status": market_health, "load_band": "high" if msg_rate >= 60 else "medium" if msg_rate else "idle", "activity_rate": msg_rate, "freshness_s": feed_age},
        {"id": "archive", "zone": "archive", "label": "Knowledge archive", "status": desk_status, "load_band": "medium" if inserted else "idle", "activity_rate": min(120.0, inserted / 5), "freshness_s": desk_age},
    ]
    links = [
        {"source": "public-edge", "target": "orchestration", "status": desk_status, "latency_ms": link_latencies.get("public-edge:orchestration"), "event_rate": max(1.0, len(agents)), "signal_class": "network"},
        {"source": "orchestration", "target": "gpu-compute", "status": gpu_status, "latency_ms": link_latencies.get("orchestration:gpu-compute"), "event_rate": service_count * 8.0, "signal_class": "agent"},
        {"source": "gpu-compute", "target": "intelligence", "status": rh_status, "latency_ms": link_latencies.get("gpu-compute:intelligence"), "event_rate": agent_rate, "signal_class": "agent"},
        {"source": "intelligence", "target": "markets", "status": market_health, "latency_ms": link_latencies.get("intelligence:markets"), "event_rate": msg_rate, "signal_class": "market"},
        {"source": "intelligence", "target": "archive", "status": desk_status, "latency_ms": link_latencies.get("intelligence:archive"), "event_rate": min(120.0, inserted / 5), "signal_class": "archive"},
    ]

    events = presence_events + [
        {
            "id": f"agent-{agent['id']}",
            "observed_at": agent["updated_at"],
            "event_class": "agent",
            "source": "intelligence",
            "target": "archive",
            "label": f"{agent['role']} status observed",
            "status": "verified" if agent["verification"] == "verified" else "degraded",
        }
        for agent in agents[:8]
        if not presence_agents or agent not in presence_agents
    ]
    if msg_rate:
        events.append({"id": f"market-{int(now)}", "observed_at": observed_at, "event_class": "market", "source": "markets", "target": "intelligence", "label": "Market activity observed", "status": "observed"})
    if inserted:
        events.append({"id": f"archive-{int(now)}", "observed_at": observed_at, "event_class": "archive", "source": "intelligence", "target": "archive", "label": "Knowledge cycle recorded", "status": "verified"})

    attention = sum(1 for node in nodes if node["status"] != "healthy")
    return {
        "version": 1,
        "observed_at": observed_at,
        "sequence": time.time_ns(),
        "summary": {"state": "degraded" if attention else "observing", "active_agents": sum(1 for agent in agents if agent["state"] in {"working", "verifying"}), "events_per_min": round(msg_rate + agent_rate, 3), "verified_today": sum(1 for agent in agents if agent["verification"] == "verified"), "attention": attention},
        "nodes": nodes,
        "links": links,
        "agents": agents,
        "markets": {"network": "Robinhood Chain", "status": market_status, "feed_age_s": feed_age, "events_per_min": msg_rate, "paper_strategies": 7 if paper else 0, "decision_gate": "telegram", "execution": "off"},
        "events": events,
    }


def signed_headers(body: bytes, secret: str, *, timestamp: int | None = None, nonce: str | None = None) -> dict[str, str]:
    if len(secret) < 32:
        raise ValueError("TELEMETRY_INGEST_SECRET must be at least 32 characters")
    ts = str(int(time.time()) if timestamp is None else timestamp)
    nonce = nonce or secrets.token_urlsafe(18)
    message = ts.encode() + b"." + nonce.encode() + b"." + body
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return {"Content-Type": "application/json", "X-Sapphire-Timestamp": ts, "X-Sapphire-Nonce": nonce, "X-Sapphire-Signature": signature}


def measure_latency_ms(endpoint: str, *, timeout: float = 2.0) -> float | None:
    """Measure one configured health endpoint without exposing its address."""
    if not endpoint:
        return None
    started = time.perf_counter()
    try:
        request = urllib.request.Request(endpoint, headers={"User-Agent": "sapphire-telemetry/1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(1)
        return round((time.perf_counter() - started) * 1000, 3)
    except (OSError, ValueError):
        return None


def configured_latencies() -> dict[str, float | None]:
    probes = {
        "public-edge:orchestration": os.getenv("SAPPHIRE_EDGE_PROBE", ""),
        "orchestration:gpu-compute": os.getenv("SAPPHIRE_COMPUTE_PROBE", ""),
        "intelligence:markets": os.getenv("SAPPHIRE_MARKETS_PROBE", ""),
        "intelligence:archive": os.getenv("SAPPHIRE_ARCHIVE_PROBE", ""),
    }
    return {link: measure_latency_ms(endpoint) for link, endpoint in probes.items()}


def push(snapshot: dict[str, Any], *, endpoint: str, secret: str, timeout: float = 10.0) -> dict[str, Any]:
    body = json.dumps(snapshot, separators=(",", ":"), allow_nan=False).encode()
    request = urllib.request.Request(endpoint, data=body, headers=signed_headers(body, secret), method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read())
    return result if isinstance(result, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or publish a privacy-safe Sapphire Mission Snapshot")
    parser.add_argument("--push", action="store_true", help="submit to SAPPHIRE_TELEMETRY_ENDPOINT")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    args = parser.parse_args()
    snapshot = build_snapshot(Sources.defaults(), link_latencies=configured_latencies())
    if args.push:
        endpoint = os.getenv("SAPPHIRE_TELEMETRY_ENDPOINT", "").strip()
        secret = os.getenv("TELEMETRY_INGEST_SECRET", "")
        if not endpoint:
            raise SystemExit("SAPPHIRE_TELEMETRY_ENDPOINT is required with --push")
        print(json.dumps(push(snapshot, endpoint=endpoint, secret=secret), sort_keys=True))
    else:
        print(json.dumps(snapshot, indent=None if args.compact else 2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

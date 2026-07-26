r"""Windows workhorse telemetry publisher for Sapphire Alpha Dashboard.

Collects agent-worker heartbeat, telegram-bot status, Ollama ps, and GPU status
from a Windows node and pushes a schema-v1 signed telemetry snapshot to:
    https://sapphirealpha.xyz/api/v1/telemetry

Environment:
    TELEMETRY_INGEST_SECRET          required for --push
    SAPPHIRE_TELEMETRY_ENDPOINT      defaults to https://sapphirealpha.xyz/api/v1/telemetry
    AGENT_WORKER_DIR                 defaults to %USERPROFILE%\agent-worker
    TELEGRAM_BOT_DIR                 defaults to %USERPROFILE%\telegram-bot
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


def _parse_bot_log_tail(path: Path) -> dict[str, Any]:
    """Parse the last 'alive' line from telegram-bot/bot.log."""
    out: dict[str, Any] = {"seen": False}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in reversed(lines):
        if "alive" not in line:
            continue
        # Expected: 2026-07-22 19:30:05 alive pid=12252 offset=... pending=1 armed=halted
        m = re.search(
            r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+alive\s+pid=(\d+)\s+offset=(\d+)\s+pending=(\d+)\s+armed=(\w+)",
            line,
        )
        if not m:
            continue
        try:
            # bot.log timestamps are written in Windows local time.
            out["seen"] = True
            out["ts"] = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
            out["pid"] = int(m.group(2))
            out["offset"] = int(m.group(3))
            out["pending"] = int(m.group(4))
            out["armed"] = m.group(5)
            return out
        except (ValueError, OSError):
            continue
    return out


def _telegram_handoff_rate_per_min(
    agent_worker_dir: Path,
    *,
    now: float,
    window_s: float = MEASUREMENT_WINDOW_SECONDS,
) -> float | None:
    """Telegram-authored worker tasks created per minute.

    ``desk.enqueue_dev`` writes a durable queue file carrying this marker before
    the bot may claim that work was dispatched. The worker later moves that same
    file from ``queue`` to ``done`` without changing its creation mtime, so the
    two directories together are an append-only view of actual handoffs.

    The previous implementation counted every timestamped ``bot.log`` line.
    Periodic ``alive`` heartbeats therefore rendered as Telegram -> worker task
    traffic even when no task crossed that edge.
    """
    if window_s <= 0:
        return None
    floor = now - window_s
    observed = 0
    marker = b"(queued from Telegram by Ari)"
    for directory in (agent_worker_dir / "queue", agent_worker_dir / "done"):
        try:
            entries = list(directory.iterdir())
        except OSError:
            # A task may be waiting in queue or may already have moved to done.
            # Seeing only one side is an incomplete window, not a measured zero.
            return None
        for entry in entries:
            try:
                modified = entry.stat().st_mtime
                if not (floor <= modified <= now) or not entry.is_file():
                    continue
                size = entry.stat().st_size
                with entry.open("rb") as handle:
                    if size > 1024:
                        handle.seek(size - 1024)
                    tail = handle.read()
            except OSError:
                continue
            if marker in tail:
                observed += 1
    return round(observed / (window_s / 60.0), 3)


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


def _pause_present(home: Path) -> bool:
    return (home / ".sapphire" / "autonomous_trading_pause").exists()


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
    telegram_bot_dir: Path | None = None,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    now: float | None = None,
) -> dict[str, Any]:
    """Build a schema-v1 telemetry snapshot from Windows-local sources."""
    now = _now() if now is None else now
    observed_at = _ts_iso(now)

    agent_worker_dir = agent_worker_dir or home / "agent-worker"
    telegram_bot_dir = telegram_bot_dir or home / "telegram-bot"

    hb = _read_json(agent_worker_dir / "heartbeat.json")
    metrics = _read_json(agent_worker_dir / "metrics.json")
    bot = _parse_bot_log_tail(telegram_bot_dir / "bot.log")
    ps = _ollama_ps(ollama_url)
    tags = _ollama_tags(ollama_url)
    gpu = _nvidia_smi()
    disk_free = _disk_free_gb()
    pause_on = _pause_present(home)

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

    # Bot freshness
    bot_timestamp = _nonnegative_number(bot.get("ts"))
    bot_age_s = (
        max(0.0, now - bot_timestamp)
        if bot.get("seen") and bot_timestamp is not None
        else 86_400.0
    )

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

    # Telegram bot health
    if bot.get("seen") and bot_age_s <= 300:
        bot_status = "healthy"
        bot_state = "working"
    elif bot.get("seen") and bot_age_s <= 900:
        bot_status = "degraded"
        bot_state = "idle"
    else:
        bot_status = "down"
        bot_state = "offline"

    # Ollama inference health
    ollama_status = "healthy" if ps["ok"] else "down"

    # Knowledge archive health (driven by worker metrics)
    archive_status = worker_status

    # Counts remain unknown when their source did not supply them. The previous
    # implementation coerced all missing values to zero, then multiplied them
    # into plausible-looking activity rates and load levels.
    loaded_models = _nonnegative_int(ps.get("loaded_count"))
    available_models = _nonnegative_int(tags.get("count"))
    pending = _nonnegative_int(bot.get("pending"))
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
    bot_message_rate = _telegram_handoff_rate_per_min(agent_worker_dir, now=now)
    archive_completion_rate = _directory_rate_per_min(agent_worker_dir / "done", now=now)
    inference_latency_ms = ps.get("latency_ms")

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
            "activity_rate": bot_message_rate,
            "freshness_s": round(min(hb_age_s, 86_400.0), 3),
        },
        {
            "id": "telegram-bot",
            "zone": "edge",
            "label": "Telegram command bot",
            "status": bot_status,
            "load_band": "medium" if bot_state == "working" or (pending is not None and pending > 0) else "idle",
            "activity_rate": bot_message_rate,
            "freshness_s": round(min(bot_age_s, 86_400.0), 3),
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
        # Durable Telegram-authored queue files per minute. The queue handoff has
        # no paired timestamps to difference, so there is no latency here.
        {"source": "telegram-bot", "target": "agent-worker", "status": worker_status, "latency_ms": None, "event_rate": bot_message_rate, "signal_class": "agent"},
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
            activity=" | ".join(
                (
                    _count_text(tasks_total, "task"),
                    _count_text(pass_count, "passing check"),
                    _count_text(fail_count, "failing check"),
                )
            ),
            verification="verified" if worker_status == "healthy" else "pending" if worker_status == "degraded" else "failed",
            provider="local GPU" if "gpu" in str(hb.get("model", "")).lower() else "local CPU",
            updated_at=_ts_iso(now - hb_age_s),
            index=0,
        ),
        _agent(
            role="Telegram command bot",
            state=bot_state,
            activity=_count_text(pending, "pending command"),
            verification="verified" if bot_status == "healthy" else "pending" if bot_status == "degraded" else "failed",
            provider="local CPU",
            updated_at=_ts_iso(now - bot_age_s) if bot.get("seen") else observed_at,
            index=1,
        ),
        _agent(
            role="Ollama inference host",
            state="working" if ps["ok"] else "offline",
            activity=f"{_count_text(loaded_models, 'loaded model')} | {_count_text(available_models, 'available model')}",
            verification="verified" if ps["ok"] else "failed",
            provider="local GPU",
            updated_at=observed_at,
            index=2,
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
            index=3,
        ),
    ]

    events: list[dict[str, Any]] = []
    if bot.get("seen"):
        events.append({
            "id": f"win-tg-{int(now)}",
            "observed_at": _ts_iso(now - bot_age_s),
            "event_class": "agent",
            "source": "edge",
            "target": "intelligence",
            "label": "Telegram bot heartbeat observed",
            "status": "verified" if bot_status == "healthy" else "degraded",
        })
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
    if pause_on:
        events.append({
            "id": f"win-pause-{int(now)}",
            "observed_at": observed_at,
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
            "attention": None,
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
            "decision_gate": "off",
            "execution": "off",
        },
        "events": events,
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
        telegram_bot_dir=Path(os.environ.get("TELEGRAM_BOT_DIR", str(home / "telegram-bot"))),
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

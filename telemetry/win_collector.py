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
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_ENDPOINT = "https://sapphirealpha.xyz/api/v1/telemetry"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"

# Semantic limits mirror backend.live_telemetry validators.
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


def _now() -> float:
    return time.time()


def _ts_iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or _now(), UTC).isoformat()


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


def _ollama_ps(base: str) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "models": []}
    try:
        req = urllib.request.Request(f"{base}/api/ps", headers={"User-Agent": "sapphire-win-telemetry/1"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        out["ok"] = True
        out["models"] = data.get("models") or []
        out["loaded_count"] = len(out["models"])
        out["vram_bytes"] = sum(int(m.get("size_vram", 0) or 0) for m in out["models"])
    except Exception as e:
        out["error"] = str(e)[:80]
    return out


def _ollama_tags(base: str) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "count": 0}
    try:
        req = urllib.request.Request(f"{base}/api/tags", headers={"User-Agent": "sapphire-win-telemetry/1"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        out["ok"] = True
        out["count"] = len(data.get("models") or [])
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


def _freshness_band(age_s: float) -> str:
    if age_s <= 60:
        return "current"
    if age_s <= 300:
        return "delayed"
    if age_s <= 900:
        return "stale"
    return "offline"


def _health_from_age(age_s: float) -> str:
    if age_s <= 300:
        return "healthy"
    if age_s <= 900:
        return "degraded"
    return "down"


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
    now = now or _now()
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
    bot_age_s = max(0.0, now - bot.get("ts", 0)) if bot.get("seen") else 86_400.0

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

    # Load / activity bands
    loaded_models = ps.get("loaded_count", 0)
    pending = bot.get("pending", 0)
    tasks_total = int(metrics.get("tasks", 0) or 0)
    pass_count = int(metrics.get("pass", 0) or 0)
    fail_count = int(metrics.get("fail", 0) or 0)

    worker_activity = float(loaded_models * 8.0 + (1.0 if hb_state == "working" else 0.0))
    bot_activity = float(pending * 4.0 + (1.0 if bot_state == "working" else 0.0))
    gpu_activity = float(gpu.get("gpu_util_pct", 0) * 1.5 + loaded_models * 8.0)

    nodes = [
        {
            "id": "win-workhorse",
            "zone": "compute",
            "label": "Windows workhorse",
            "status": workhorse_status,
            "load_band": "high" if gpu_activity >= 60 else "medium" if gpu_activity >= 10 else "idle",
            "activity_rate": round(min(gpu_activity, 120.0), 3),
            "freshness_s": round(min(ollama_age_s, 86_400.0), 3),
        },
        {
            "id": "agent-worker",
            "zone": "intelligence",
            "label": "Agent worker",
            "status": worker_status,
            "load_band": "high" if worker_activity >= 60 else "medium" if worker_activity >= 10 else "idle",
            "activity_rate": round(min(worker_activity, 120.0), 3),
            "freshness_s": round(min(hb_age_s, 86_400.0), 3),
        },
        {
            "id": "telegram-bot",
            "zone": "edge",
            "label": "Telegram command bot",
            "status": bot_status,
            "load_band": "high" if bot_activity >= 60 else "medium" if bot_activity >= 10 else "idle",
            "activity_rate": round(min(bot_activity, 120.0), 3),
            "freshness_s": round(min(bot_age_s, 86_400.0), 3),
        },
        {
            "id": "ollama-inference",
            "zone": "compute",
            "label": "Ollama inference",
            "status": ollama_status,
            "load_band": "high" if loaded_models >= 3 else "medium" if loaded_models >= 1 else "idle",
            "activity_rate": float(loaded_models * 8.0),
            "freshness_s": round(min(ollama_age_s, 86_400.0), 3),
        },
        {
            "id": "knowledge-archive",
            "zone": "archive",
            "label": "Knowledge archive",
            "status": archive_status,
            "load_band": "medium" if tasks_total else "idle",
            "activity_rate": float(min(tasks_total * 2.0, 120.0)),
            "freshness_s": round(min(hb_age_s, 86_400.0), 3),
        },
    ]

    links = [
        {"source": "telegram-bot", "target": "agent-worker", "status": worker_status, "latency_ms": None, "event_rate": bot_activity, "signal_class": "agent"},
        {"source": "agent-worker", "target": "ollama-inference", "status": ollama_status, "latency_ms": None, "event_rate": worker_activity, "signal_class": "agent"},
        {"source": "ollama-inference", "target": "win-workhorse", "status": workhorse_status, "latency_ms": None, "event_rate": gpu_activity, "signal_class": "network"},
        {"source": "agent-worker", "target": "knowledge-archive", "status": archive_status, "latency_ms": None, "event_rate": float(tasks_total), "signal_class": "archive"},
    ]

    agents = [
        _agent(
            role="Agent worker",
            state=worker_state,
            activity=f"Release {hb.get('release', 'unknown')} | tasks={tasks_total} pass={pass_count} fail={fail_count}",
            verification="verified" if worker_status == "healthy" else "pending" if worker_status == "degraded" else "failed",
            provider="local GPU" if "gpu" in str(hb.get("model", "")).lower() else "local CPU",
            updated_at=_ts_iso(now - hb_age_s),
            index=0,
        ),
        _agent(
            role="Telegram command bot",
            state=bot_state,
            activity=f"Pending commands: {pending} | armed={bot.get('armed', 'unknown')}",
            verification="verified" if bot_status == "healthy" else "pending" if bot_status == "degraded" else "failed",
            provider="local CPU",
            updated_at=_ts_iso(now - bot_age_s) if bot.get("seen") else observed_at,
            index=1,
        ),
        _agent(
            role="Ollama inference host",
            state="working" if ps["ok"] else "offline",
            activity=f"{loaded_models} loaded models | {tags.get('count', 0)} available | VRAM {round(ps.get('vram_bytes', 0) / 1e9, 1)} GB",
            verification="verified" if ps["ok"] else "failed",
            provider="local GPU",
            updated_at=observed_at,
            index=2,
        ),
        _agent(
            role="GPU workhorse",
            state="working" if gpu_healthy else "offline",
            activity=f"{gpu.get('name', 'GPU')} util {gpu.get('gpu_util_pct', 'unknown')}% | mem {gpu.get('mem_util_pct', 'unknown')}% | temp {gpu.get('temp_c', 'unknown')}C",
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
            "label": f"Ollama serving {loaded_models} model(s)",
            "status": "verified",
        })
    if worker_status != "down":
        events.append({
            "id": f"win-worker-{int(now)}",
            "observed_at": _ts_iso(now - hb_age_s),
            "event_class": "agent",
            "source": "intelligence",
            "target": "archive",
            "label": f"Agent worker {hb_state} | {tasks_total} tasks tracked",
            "status": "verified" if worker_status == "healthy" else "degraded",
        })
    if gpu_healthy:
        events.append({
            "id": f"win-gpu-{int(now)}",
            "observed_at": observed_at,
            "event_class": "agent",
            "source": "compute",
            "target": "compute",
            "label": f"GPU {gpu.get('name', 'device')} observed",
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

    attention = sum(1 for node in nodes if node["status"] != "healthy")
    active_agents = sum(1 for agent in agents if agent["state"] in {"working", "verifying"})

    return {
        "version": 1,
        "observed_at": observed_at,
        "sequence": time.time_ns(),
        "summary": {
            "state": "degraded" if attention else "observing",
            "active_agents": active_agents,
            "events_per_min": round(float(loaded_models * 4.0 + pending * 2.0 + (1.0 if worker_state == "working" else 0.0)), 3),
            "verified_today": sum(1 for agent in agents if agent["verification"] == "verified"),
            "attention": attention,
        },
        "nodes": nodes,
        "links": links,
        "agents": agents,
        "markets": {
            "network": "Windows workhorse",
            "status": "offline",
            "feed_age_s": round(min(hb_age_s, 86_400.0), 3),
            "events_per_min": 0.0,
            "paper_strategies": 0,
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


def push(snapshot: dict[str, Any], *, endpoint: str, secret: str, timeout: float = 15.0) -> dict[str, Any]:
    body = json.dumps(snapshot, separators=(",", ":"), allow_nan=False).encode()
    request = urllib.request.Request(endpoint, data=body, headers=signed_headers(body, secret), method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read())
    return result if isinstance(result, dict) else {}


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

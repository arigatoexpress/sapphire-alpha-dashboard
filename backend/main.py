"""
Sapphire Alpha Dashboard — unified, privacy-preserving trading & business control plane.

Public endpoints:
  GET /healthz

Authenticated endpoints (HTTP Basic Auth):
  GET /api/v1/status
  GET /api/v1/widgets
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

log = logging.getLogger("sapphire-alpha-dashboard")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Sapphire Alpha Dashboard", version="0.1.0")
security = HTTPBasic()

_FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _mask_address(addr: str | None) -> str | None:
    """Render a blockchain address as pseudonymous 0xabcd...1234."""
    if not addr or not addr.startswith("0x") or len(addr) < 10:
        return addr
    return f"{addr[:6]}...{addr[-4:]}"


def _safe_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.lower() in {"1", "true", "yes", "on"}
    return bool(raw)


@lru_cache(maxsize=1)
def _auth_credentials() -> tuple[str, str]:
    username = _env("AUTH_USERNAME", "sapphire")
    password = _env("AUTH_PASSWORD", "")
    if not password:
        raise RuntimeError("AUTH_PASSWORD environment variable must be set")
    weak = {"sapphire", "password", "changeme", "admin", "123456"}
    if password.lower() in weak:
        raise RuntimeError("AUTH_PASSWORD is too weak")
    return username, password


def require_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    expected_user, expected_pass = _auth_credentials()
    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), expected_user.encode("utf-8")
    )
    pass_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), expected_pass.encode("utf-8")
    )
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "sapphire-alpha-dashboard",
        "version": "0.1.0",
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _read_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("failed to read %s: %s", path, exc)
    return None


def _gate_status() -> dict[str, Any]:
    """Aggregate trading gate state from canonical state files or env."""
    home = Path.home()
    gate = _read_json(home / "ops-state" / "rh-chain" / "gate.json") or {}
    skin = _read_json(home / "ops-state" / "rh-chain" / "skin-book.json") or {}
    pause = home / ".sapphire" / "autonomous_trading_pause"
    box_pause = Path("C:/Users/aribs/.sapphire/autonomous_trading_pause")

    armed = _safe_bool(gate.get("armed", skin.get("armed", False)))
    mode = gate.get("mode") or skin.get("mode") or "telegram"
    killswitch = pause.exists() or box_pause.exists() or _safe_bool(
        os.environ.get("DASHBOARD_FORCE_KILLSWITCH", "")
    )

    if killswitch:
        state = "killswitch"
        label = "Killswitch engaged"
    elif armed:
        state = "armed"
        label = "Armed — Telegram gate"
    else:
        state = "disarmed"
        label = "Disarmed"

    wallet_addr = _env("WALLET_ADDRESS") or skin.get("wallet_address")
    return {
        "state": state,
        "label": label,
        "armed": armed,
        "killswitch": killswitch,
        "mode": mode,
        "wallet_address": _mask_address(wallet_addr),
        "cap_usd": int(_env("MAX_ORDER_USD", "25")),
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _telegram_queue() -> dict[str, Any]:
    """Surface Telegram approval queue length without exposing chat IDs."""
    queue_path = Path.home() / "ops-state" / "telegram-bot" / "pending_queue.json"
    data = _read_json(queue_path) or []
    pending = len(data) if isinstance(data, list) else 0
    return {
        "pending": pending,
        "gate": "telegram",
        "status": "polling" if _safe_bool(_env("TELEGRAM_BOT_POLLING", "true")) else "paused",
        "recent_count": min(pending, 5),
    }


def _recent_signals() -> list[dict[str, Any]]:
    """Recent trading signals with synthetic identifiers only."""
    signals_path = Path.home() / "ops-state" / "rh-chain" / "signals.json"
    data = _read_json(signals_path)
    if isinstance(data, list):
        return [
            {
                "id": f"sig-{i+1:03d}",
                "instrument": s.get("instrument", "UNKNOWN"),
                "side": s.get("side", "-"),
                "venue": s.get("venue", "manual"),
                "confidence": s.get("confidence", "medium"),
                "timestamp": s.get("timestamp", datetime.now(UTC).isoformat()),
            }
            for i, s in enumerate(data[:8])
        ]
    # Graceful mock when no signal file is available (Cloud Run default).
    return [
        {
            "id": "sig-001",
            "instrument": "RICH",
            "side": "BUY",
            "venue": "on_chain",
            "confidence": "high",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    ]


def _defi_report_feed() -> dict[str, Any]:
    """DeFi Report clip feed — aggregate only, no subscriber PII."""
    clips_dir = Path.home() / "Knowledge" / "3-Resources" / "Clippings"
    clips: list[dict[str, Any]] = []
    if clips_dir.exists():
        for p in sorted(clips_dir.glob("*.md"), reverse=True)[:6]:
            lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
            title = next(
                (l.lstrip("# ").strip() for l in lines if l.strip().startswith("# ")), p.stem
            )
            clips.append({"id": p.stem, "title": title, "source": "tdr_pro"})
    if not clips:
        clips = [
            {"id": "tdr-001", "title": "DeFi Report — weekly rollup", "source": "tdr_pro"},
        ]
    return {"clips": clips, "source": "tdr_pro", "live": _safe_bool(_env("TDR_PRO_LIVE", "0"))}


def _tradingview_status() -> dict[str, Any]:
    """TradingView webhook pipeline status."""
    return {
        "status": _env("TV_WEBHOOK_STATUS", "standby"),
        "endpoint": _env("TV_WEBHOOK_URL", "not configured"),
        "last_ping": _env("TV_LAST_PING", datetime.now(UTC).isoformat()),
        "pending_alerts": int(_env("TV_PENDING_ALERTS", "0")),
    }


def _system_health() -> dict[str, Any]:
    """High-level system health aggregates."""
    return {
        "dashboard": "ok",
        "gate": _gate_status()["state"],
        "telegram": _telegram_queue()["status"],
        "tradingview": _tradingview_status()["status"],
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/api/v1/status")
async def api_status(user: str = Depends(require_auth)) -> dict[str, Any]:
    return {
        "service": "sapphire-alpha-dashboard",
        "authenticated_user": user,
        "gate": _gate_status(),
        "system_health": _system_health(),
    }


@app.get("/api/v1/widgets")
async def api_widgets(user: str = Depends(require_auth)) -> dict[str, Any]:
    return {
        "gate": _gate_status(),
        "telegram_queue": _telegram_queue(),
        "recent_signals": _recent_signals(),
        "defi_report": _defi_report_feed(),
        "tradingview": _tradingview_status(),
        "system_health": _system_health(),
        "rendered_at": datetime.now(UTC).isoformat(),
    }


@app.get("/assets/{filename}")
async def frontend_assets(filename: str, user: str = Depends(require_auth)) -> FileResponse:
    path = _FRONTEND_DIST_DIR / "assets" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path)


@app.get("/{catchall:path}")
async def frontend_root(catchall: str, user: str = Depends(require_auth)) -> FileResponse:
    # SPA catch-all: return index.html for any non-API route.
    index = _FRONTEND_DIST_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=503, detail="frontend bundle not built")
    return FileResponse(index)


@app.exception_handler(Exception)
async def _generic_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "internal error"},
    )

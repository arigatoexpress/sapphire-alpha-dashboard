"""
Sapphire Alpha Dashboard — Mission Control.

Public endpoints:
  GET /healthz
  GET /api/health

Authenticated endpoints (HTTP Basic Auth):
  GET /api/v1/status
  GET /api/v1/widgets
  GET /api/v1/transparency

Public read-only mode (PUBLIC_READ_ONLY=1):
  Anonymous GETs to the frontend, /assets/*, /api/v1/status, /api/v1/widgets and
  /api/v1/tradingview/alerts are allowed but served a whitelist-sanitized payload
  (no internal URLs/hostnames, no proposal bodies, no exact capital figures, no
  limits/caps, no file paths). Authenticated users always get the full payload.
  /vault/rag-map ALWAYS requires auth regardless of PUBLIC_READ_ONLY.
"""

from __future__ import annotations

import base64
import html
import json
import logging
import os
import re
import secrets
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

try:
    from . import telegram_miniapp, transparency
    from .live_telemetry import TelemetryValidationError, store as live_telemetry_store
    from .moss_telemetry import MossTelemetryValidationError, store as moss_telemetry_store
except ImportError:  # Tests import `main` directly from backend/.
    import telegram_miniapp
    import transparency
    from live_telemetry import TelemetryValidationError, store as live_telemetry_store
    from moss_telemetry import MossTelemetryValidationError, store as moss_telemetry_store

log = logging.getLogger("sapphire-alpha-dashboard")
logging.basicConfig(level=logging.INFO)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Sapphire Alpha Dashboard", version="0.2.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
security = HTTPBasic()
security_optional = HTTPBasic(auto_error=False)

PUBLIC_USER = "public"


def _public_read_only() -> bool:
    """Whether anonymous read-only access is enabled (checked per request)."""
    return _safe_bool(_env("PUBLIC_READ_ONLY", ""))


def _api_rate_limit() -> str:
    """Tighter limiter on API routes while the dashboard is publicly readable."""
    return "20/minute" if _public_read_only() else "60/minute"


@app.middleware("http")
async def _reject_path_traversal(request: Request, call_next: Any) -> Response:
    # FastAPI normalizes paths before routing; reject any raw path containing '..'.
    if ".." in request.url.path.split("/"):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "forbidden"},
        )
    return await call_next(request)

# CORS: default deny; allow configured origin only.
_cors_origin = _env("CORS_ORIGIN", "")
if _cors_origin:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_cors_origin],
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["Authorization"],
    )


@app.middleware("http")
async def _security_headers(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


_FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# Statically exported Next.js marketing site (`web/`). Served from this same
# container so the public site, the operator dashboard, and the API share one
# Cloud Run service and one domain.
_WEB_OUT_DIR = Path(__file__).resolve().parent.parent / "web" / "out"

# Explicit map rather than `mimetypes.guess_type`, which depends on the host's
# mime database and would vary between a Mac dev box and the slim container.
_MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".xml": "application/xml",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".webmanifest": "application/manifest+json",
}

# Next.js emits metadata images with no file extension (`out/opengraph-image`).
# Without an explicit type these serve as octet-stream and social unfurlers
# silently drop the preview image.
_EXTENSIONLESS_MEDIA_TYPES = {
    "opengraph-image": "image/png",
    "twitter-image": "image/png",
    "icon": "image/png",
    "apple-icon": "image/png",
}


def _media_type_for(path: Path) -> str:
    if not path.suffix:
        return _EXTENSIONLESS_MEDIA_TYPES.get(path.name, "application/octet-stream")
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def _resolve_static(root: Path, relative: str) -> Path | None:
    """Resolve `relative` to a file inside `root`, or None.

    Tries the literal path, then `.html`, then `index.html` — covering how the
    Next.js export names routes. Any candidate that escapes `root` after
    symlink resolution is refused, so a crafted path cannot read the image.
    """
    if not root.is_dir():
        return None
    try:
        base = root.resolve(strict=True)
    except OSError:
        return None

    cleaned = relative.strip("/")
    candidates = ("index.html",) if not cleaned else (
        cleaned,
        f"{cleaned}.html",
        f"{cleaned}/index.html",
    )

    for candidate in candidates:
        try:
            path = (base / candidate).resolve(strict=False)
        except (ValueError, RuntimeError, OSError):
            continue
        if not path.is_relative_to(base):
            continue
        if path.is_file():
            return path
    return None


def _static_file_response(path: Path, cache: str) -> FileResponse:
    return FileResponse(
        path,
        media_type=_media_type_for(path),
        headers={"Cache-Control": cache},
    )


# The marketing site is the public front door and must never sit behind Basic
# auth — unlike the operator dashboard, which keeps `auth_or_public`.
_MARKETING_CACHE = "public, max-age=0, must-revalidate"
# Next.js fingerprints every filename under /_next/static, so these are immutable.
_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"

# Canonical local state paths (Mac). Cloud Run uses env overrides.
_HOME = Path.home()
_RH_CHAIN_DIR = _HOME / "ops-state" / "rh-chain"
_TELEGRAM_DIR = _HOME / "ops-state" / "telegram-bot"
_KNOWLEDGE_CLIPS_DIR = _HOME / "Knowledge" / "3-Resources" / "Clippings"


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


def _safe_float(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def _auth_credentials() -> tuple[str, str]:
    username = _env("AUTH_USERNAME", "sapphire").strip()
    password = _env("AUTH_PASSWORD", "")
    secret_path = _env("AUTH_PASSWORD_SECRET", "")
    if secret_path:
        try:
            password = Path(secret_path).read_text(encoding="utf-8").strip()
        except Exception as exc:
            raise RuntimeError(f"Failed to read AUTH_PASSWORD_SECRET at {secret_path}: {exc}") from exc
    if not password:
        raise RuntimeError("AUTH_PASSWORD environment variable or AUTH_PASSWORD_SECRET file must be set")
    if len(password) < 12:
        raise RuntimeError("AUTH_PASSWORD must be at least 12 characters")
    weak = {"sapphire", "password", "changeme", "admin", "123456", "sapphirealpha"}
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


def auth_or_public(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security_optional),
) -> str:
    """Allow anonymous GETs when PUBLIC_READ_ONLY is enabled; otherwise require auth.

    Presented credentials are always validated (bad creds never fall back to the
    anonymous path). Non-GET methods always require auth.
    """
    if credentials is not None:
        return require_auth(credentials)
    if _public_read_only() and request.method == "GET":
        return PUBLIC_USER
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Basic"},
    )


@app.get("/healthz")
@limiter.limit("30/minute")
async def healthz(request: Request) -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "sapphire-alpha-dashboard",
        "version": "0.2.0",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/api/health")
@limiter.limit("30/minute")
async def api_health(request: Request) -> dict[str, Any]:
    """Public health endpoint that avoids Cloud Run /healthz interception."""
    return await healthz(request)


def _reset_live_telemetry_for_tests() -> None:
    """Reset the in-memory test backend; production persistence never deletes."""
    live_telemetry_store.reset()


def _reset_moss_telemetry_for_tests() -> None:
    """Reset the in-memory MOSS test backend; production persistence never deletes."""
    moss_telemetry_store.reset()


@app.post("/api/v1/telemetry", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("120/minute")
async def ingest_live_telemetry(request: Request) -> dict[str, Any]:
    """Accept one HMAC-signed semantic snapshot from the local collector."""
    body = await request.body()
    if len(body) > 64 * 1024:
        raise HTTPException(status_code=413, detail="telemetry body too large")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="invalid telemetry JSON") from None
    try:
        snapshot = live_telemetry_store.accept(
            body=body,
            headers={key.lower(): value for key, value in request.headers.items()},
            secret=_env("TELEMETRY_INGEST_SECRET", ""),
            parsed_json=payload,
        )
    except OverflowError:
        raise HTTPException(status_code=413, detail="telemetry body too large") from None
    except PermissionError:
        raise HTTPException(status_code=401, detail="invalid telemetry signature") from None
    except FileExistsError:
        raise HTTPException(status_code=409, detail="telemetry replay rejected") from None
    except RuntimeError:
        raise HTTPException(status_code=503, detail="telemetry ingest unavailable") from None
    except TelemetryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {"accepted": True, "sequence": snapshot["sequence"]}


@app.get("/api/v1/live")
@limiter.limit(_api_rate_limit)
async def api_live(request: Request, user: str = Depends(auth_or_public)) -> dict[str, Any]:
    """Serve the current operator snapshot or delayed public projection."""
    public = user == PUBLIC_USER
    try:
        delay_seconds = max(0.0, min(300.0, float(_env("PUBLIC_TELEMETRY_DELAY_SECONDS", "15"))))
    except ValueError:
        delay_seconds = 15.0
    return live_telemetry_store.get(public=public, delay_seconds=delay_seconds)


@app.post("/api/v1/moss/telemetry", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("120/minute")
async def ingest_moss_telemetry(request: Request) -> dict[str, Any]:
    """Accept one HMAC-signed, masked MOSS observation from the home projector."""
    body = await request.body()
    if len(body) > 8 * 1024:
        raise HTTPException(status_code=413, detail="MOSS telemetry body too large")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="invalid MOSS telemetry JSON") from None
    try:
        snapshot = moss_telemetry_store.accept(
            body=body,
            headers={key.lower(): value for key, value in request.headers.items()},
            secret=_env("MOSS_TELEMETRY_INGEST_SECRET", ""),
            parsed_json=payload,
        )
    except OverflowError:
        raise HTTPException(status_code=413, detail="MOSS telemetry body too large") from None
    except PermissionError:
        raise HTTPException(status_code=401, detail="invalid MOSS telemetry signature") from None
    except FileExistsError:
        raise HTTPException(status_code=409, detail="MOSS telemetry replay rejected") from None
    except RuntimeError:
        raise HTTPException(status_code=503, detail="MOSS telemetry ingest unavailable") from None
    except (MossTelemetryValidationError, TelemetryValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {"accepted": True, "sequence": snapshot["sequence"]}


@app.get("/api/v1/moss")
@limiter.limit(_api_rate_limit)
async def api_moss(request: Request, user: str = Depends(auth_or_public)) -> dict[str, Any]:
    """Serve exact operator detail or a banded anonymous MOSS projection."""
    public = user == PUBLIC_USER
    try:
        delay_seconds = max(0.0, min(300.0, float(_env("PUBLIC_TELEMETRY_DELAY_SECONDS", "15"))))
    except ValueError:
        delay_seconds = 15.0
    return moss_telemetry_store.get(public=public, delay_seconds=delay_seconds)


@app.get("/api/v1/transparency")
@limiter.limit(_api_rate_limit)
async def api_transparency(
    request: Request, user: str = Depends(auth_or_public)
) -> dict[str, Any]:
    """Explanation-ledger pane: operator full detail or sanitized public bands."""
    public = user == PUBLIC_USER
    ledger = Path(_env("DASHBOARD_EXPLANATIONS_PATH", "")
                  or (_TELEGRAM_DIR / transparency.LEDGER_NAME))
    return transparency.snapshot(ledger, public=public)


def _read_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("failed to read %s: %s", path, exc)
    return None


def _read_jsonl(path: Path, limit: int = 20) -> list[dict[str, Any]]:
    """Read the last `limit` JSON lines from a file."""
    rows: list[dict[str, Any]] = []
    try:
        if not path.exists():
            return rows
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    rows.append(obj)
            except json.JSONDecodeError:
                continue
    except Exception as exc:
        log.warning("failed to read jsonl %s: %s", path, exc)
    return rows[-limit:] if limit else rows


def _sanitize_proposal(raw: dict[str, Any], idx: int) -> dict[str, Any]:
    """Strip PII from a Telegram proposal/decision and return display-safe fields."""
    # Drop any key that looks like PII.
    pii_keys = {"chat_id", "user_id", "username", "first_name", "last_name", "phone", "email"}
    safe: dict[str, Any] = {}
    for key, value in raw.items():
        low = key.lower()
        if low in pii_keys or "secret" in low or "password" in low or "token" in low:
            continue
        if low in {"wallet_address", "address"} and isinstance(value, str):
            safe[key] = _mask_address(value)
        else:
            safe[key] = value

    out: dict[str, Any] = {
        "id": f"prop-{idx:03d}",
        "action": safe.get("action", safe.get("type", "proposal")),
        "instrument": safe.get("instrument", safe.get("symbol", "—")),
        "side": safe.get("side", "—"),
        "confidence": safe.get("confidence", "medium"),
        "status": safe.get("status", "pending"),
        "timestamp": safe.get("timestamp", safe.get("created_at", datetime.now(UTC).isoformat())),
    }
    if "wallet_address" in safe:
        out["wallet_address"] = safe["wallet_address"]
    return out


def _executor_heartbeat() -> dict[str, Any]:
    """Executor liveness from local heartbeat or env override."""
    env = _env("DASHBOARD_EXECUTOR_HEARTBEAT", "").strip()
    data: dict[str, Any] = {}
    if env:
        try:
            data = json.loads(env)
        except json.JSONDecodeError:
            data = {"status": env}
    else:
        data = _read_json(_RH_CHAIN_DIR / "executor-heartbeat.json") or {}

    status_str = str(data.get("status", "unknown")).lower()
    alive = status_str in {"alive", "ok", "running", "healthy"} or _safe_bool(data.get("alive"))
    return {
        "status": status_str if status_str not in {"", "none"} else "unknown",
        "alive": alive,
        "last_seen": data.get("last_seen") or data.get("timestamp") or data.get("epoch"),
        "pid": data.get("pid"),
    }


def _skin_book() -> dict[str, Any]:
    """Read skin book from canonical file or env override."""
    env = _env("DASHBOARD_SKIN_BOOK", "").strip()
    data: dict[str, Any] = {}
    if env:
        try:
            data = json.loads(env)
        except json.JSONDecodeError:
            data = {}
    else:
        data = _read_json(_RH_CHAIN_DIR / "skin-book.json") or {}

    positions = data.get("positions", [])
    fills = data.get("fills", [])
    return {
        "updated_at": datetime.fromtimestamp(data.get("updated", 0), UTC).isoformat()
        if data.get("updated")
        else datetime.now(UTC).isoformat(),
        "mode": data.get("mode", "telegram"),
        "banner": data.get("banner", "Skin book"),
        "deployed_usd": _safe_float(data.get("deployed_usd")),
        "n_open": int(data.get("n_open", len(positions))),
        "positions_count": len(positions),
        "fills_count": len(fills),
        "skin_in_game": _safe_bool(data.get("skin_in_game", False)),
        "limits": data.get("limits", {}),
    }


def _gate_status() -> dict[str, Any]:
    """Aggregate trading gate state from canonical state files or env."""
    gate = _read_json(_RH_CHAIN_DIR / "gate.json") or {}
    skin = _read_json(_RH_CHAIN_DIR / "skin-book.json") or {}
    pause = _HOME / ".sapphire" / "autonomous_trading_pause"
    box_pause = Path("C:/Users/aribs/.sapphire/autonomous_trading_pause")

    # Env overrides allow the dashboard to reflect state when running on Cloud Run
    # without access to the user's local filesystem.
    env_armed = os.environ.get("DASHBOARD_ARMED", "")
    env_mode = os.environ.get("DASHBOARD_MODE", "")
    env_killswitch = os.environ.get("DASHBOARD_FORCE_KILLSWITCH", "")

    armed = _safe_bool(env_armed) if env_armed else _safe_bool(gate.get("armed", skin.get("armed", False)))
    mode = env_mode or gate.get("mode") or skin.get("mode") or "telegram"
    killswitch = _safe_bool(env_killswitch) if env_killswitch else (pause.exists() or box_pause.exists())

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
        "executor_alive": _executor_heartbeat()["alive"],
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _wallet_status() -> dict[str, Any]:
    """Privacy-preserving wallet / PnL tile."""
    skin = _skin_book()
    wallet_addr = _env("WALLET_ADDRESS") or (_read_json(_RH_CHAIN_DIR / "skin-book.json") or {}).get("wallet_address")
    return {
        "address": _mask_address(wallet_addr),
        "deployed_usd": skin["deployed_usd"],
        "n_open": skin["n_open"],
        "positions_count": skin["positions_count"],
        "fills_count": skin["fills_count"],
        "skin_in_game": skin["skin_in_game"],
        "limits": skin["limits"],
        "updated_at": skin["updated_at"],
    }


def _magnum_status() -> dict[str, Any]:
    """Magnum Opus overnight lab — local harness projection (read-only)."""
    gate = _read_json(_RH_CHAIN_DIR / "gate.json") or {}
    fr = _read_json(_RH_CHAIN_DIR / "free-reign.json") or {}
    l2 = _read_json(_RH_CHAIN_DIR / "l2-wallet-snapshot.json") or {}
    adapt = _read_json(_RH_CHAIN_DIR / "overnight-adapt.json") or {}
    health = _read_json(_RH_CHAIN_DIR / "agent-health-state.json") or {}
    night = _read_json(_HOME / "ops-state" / "sov-lab" / "night" / "latest.json") or {}
    moss = _read_json(_HOME / "ops-state" / "moss" / "session.json") or {}
    limits = fr.get("limits") if isinstance(fr.get("limits"), dict) else {}
    top = (adapt.get("universe") or {}).get("top_fillable_candidates") or []
    candidates = [
        str(t.get("symbol") or "")
        for t in top[:8]
        if isinstance(t, dict) and t.get("symbol")
    ]
    moss_ok = bool(moss) and not moss.get("revoked")
    moss_exp = moss.get("expiry")
    return {
        "product": "magnum-opus",
        "gate_armed": _safe_bool(gate.get("armed")),
        "mode": gate.get("mode") or "—",
        "free_reign": _safe_bool(fr.get("enabled")),
        "daily_cap_usd": limits.get("daily_cap_usd"),
        "per_trade_verified_usd": limits.get("per_trade_cap_verified_usd"),
        "per_trade_thesis_usd": limits.get("per_trade_cap_thesis_usd"),
        "l2_eth": l2.get("eth"),
        "l2_address_masked": _mask_address(l2.get("address")),
        "health": health.get("overall") or "—",
        "night_severity": night.get("severity") or "—",
        "night_issues": list(night.get("issues") or [])[:5],
        "moss_ok": moss_ok,
        "moss_expiry": moss_exp,
        "candidates": candidates,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _telegram_queue() -> dict[str, Any]:
    """Surface Telegram approval queue length and recent proposals without exposing chat IDs."""
    queue_path = _TELEGRAM_DIR / "pending_queue.json"
    decisions_path = _TELEGRAM_DIR / "decisions.jsonl"

    data = _read_json(queue_path)
    pending = len(data) if isinstance(data, list) else 0

    decisions = _read_jsonl(decisions_path, limit=10)
    proposals = [_sanitize_proposal(d, i + 1) for i, d in enumerate(decisions)]

    # If a pending_queue.json entry is a dict, treat it as a proposal too.
    if isinstance(data, list):
        for i, item in enumerate(data[:10]):
            if isinstance(item, dict):
                proposals.insert(0, _sanitize_proposal(item, len(proposals) + 1))

    return {
        "pending": pending,
        "gate": "telegram",
        "status": "polling" if _safe_bool(_env("TELEGRAM_BOT_POLLING", "true")) else "paused",
        "recent_count": min(pending, 5),
        "proposals": proposals[:8],
    }


def _recent_signals() -> list[dict[str, Any]]:
    """Recent observed trading signals with synthetic display identifiers."""
    env = _env("DASHBOARD_SIGNALS_JSON", "").strip()
    data: Any = None
    if env:
        try:
            data = json.loads(env)
        except json.JSONDecodeError:
            data = None
    if data is None:
        data = _read_json(_RH_CHAIN_DIR / "signals.json")

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
            for i, s in enumerate(data[:12])
        ]
    # Missing observations must stay visibly empty; production never fabricates alpha.
    return []


def _parse_tdr_rss(xml_text: str) -> list[dict[str, Any]]:
    """Minimal parser for The DeFi Report podcast RSS feed."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    channel = root.find("channel")
    if channel is None:
        return []

    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].lower()

    def _first_text(element: ET.Element, *names: str) -> str:
        wanted = {name.lower() for name in names}
        for child in element:
            if _local_name(child.tag) in wanted:
                return "".join(child.itertext()).strip()
        return ""

    def _strip_html(value: str) -> str:
        text = str(value or "")
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    clips: list[dict[str, Any]] = []
    for item in channel.findall("item"):
        title = _strip_html(_first_text(item, "title"))
        guid = _first_text(item, "guid") or _first_text(item, "link")
        link = _first_text(item, "link")
        if not guid:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80] or "tdr-episode"
        clips.append({"id": slug, "title": title or "Untitled TDR episode", "source": "tdr_pro", "path": link or ""})
    return clips


async def _fetch_tdr_rss() -> list[dict[str, Any]]:
    """Fetch the public TDR Pro RSS feed directly from Cloud Run."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get("https://feeds.transistor.fm/the-defi-report")
        if r.status_code == 200:
            return _parse_tdr_rss(r.text)[:8]
        log.warning("TDR Pro RSS returned HTTP %s", r.status_code)
    except Exception as exc:
        log.warning("failed to fetch TDR Pro RSS: %s", exc)
    return []


async def _defi_report_feed() -> dict[str, Any]:
    """DeFi Report clip feed — aggregate only, no subscriber PII.

    Local clippings take precedence. When running on Cloud Run without access to
    the Mac filesystem, pass ``DASHBOARD_TDR_CLIPS_JSON`` as a JSON array of
    clip objects, or ``DASHBOARD_TDR_JSON`` pointing to a local JSON summary file.
    The env value may be base64-encoded to survive shell/gcloud substitution parsing.

    As a last resort, the backend can fetch the public RSS feed directly when
    ``TDR_PRO_LIVE=1``.
    """
    clips: list[dict[str, Any]] = []

    env_clips = _env("DASHBOARD_TDR_CLIPS_JSON", "").strip()
    if env_clips:
        raw = env_clips
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except Exception:
            pass
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                clips = parsed[:8]
        except json.JSONDecodeError:
            log.warning("DASHBOARD_TDR_CLIPS_JSON is not valid JSON")

    if not clips:
        env_summary = _env("DASHBOARD_TDR_JSON", "").strip()
        if env_summary:
            try:
                path = Path(env_summary)
                if path.exists():
                    data = json.loads(path.read_text(encoding="utf-8"))
                    for ep in data.get("episodes", [])[:8]:
                        clips.append(
                            {
                                "id": ep.get("slug", "tdr-000"),
                                "title": ep.get("title", "TDR Pro episode"),
                                "source": "tdr_pro",
                                "path": "",
                            }
                        )
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("failed to read DASHBOARD_TDR_JSON: %s", exc)

    if not clips:
        clips_dir = _KNOWLEDGE_CLIPS_DIR
        if clips_dir.exists():
            for p in sorted(clips_dir.glob("*.md"), reverse=True)[:8]:
                lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
                title = next(
                    (l.lstrip("# ").strip() for l in lines if l.strip().startswith("# ")), p.stem
                )
                clips.append({"id": p.stem, "title": title, "source": "tdr_pro", "path": str(p)})

    live = _safe_bool(_env("TDR_PRO_LIVE", "0"))
    if live and not clips:
        clips = await _fetch_tdr_rss()

    if not clips:
        clips = [
            {"id": "tdr-001", "title": "DeFi Report — weekly rollup", "source": "tdr_pro", "path": ""},
        ]
    return {"clips": clips, "source": "tdr_pro", "live": live or bool(clips and clips[0]["id"] != "tdr-001")}


# Lightweight cache so a 30s dashboard poll does not hammer the Windows webhook.
_tv_probe_cache: dict[str, Any] = {"ts": 0.0, "result": None}
_TV_PROBE_TTL_SECONDS = 15.0


async def _probe_tradingview_webhook() -> dict[str, Any]:
    """Probe the TradingView webhook receiver health endpoint.

    Uses TV_WEBHOOK_URL env (e.g. https://webhook.sapphirealpha.xyz/webhook/health
    or an authenticated private-mesh health endpoint). Falls back
    to env stub when no URL is configured.
    """
    now = datetime.now(UTC).timestamp()
    cached = _tv_probe_cache["result"]
    if cached and (now - _tv_probe_cache["ts"]) < _TV_PROBE_TTL_SECONDS:
        return cached

    url = _env("TV_WEBHOOK_URL", "").strip()
    if not url or url == "not configured":
        result = {
            "status": "standby",
            "endpoint": "not configured",
            "last_ping": datetime.now(UTC).isoformat(),
            "pending_alerts": 0,
            "recent_log": [],
            "probe": {"name": "tradingview_webhook", "status": "not_configured"},
        }
        _tv_probe_cache.update({"ts": now, "result": result})
        return result

    health_url = url.rstrip("/") + "/webhook/health"
    probe = await _probe_health("tradingview_webhook", health_url, timeout=3.0)
    status_label = "ok" if probe["status"] == "ok" else "degraded"
    pending_alerts = 0
    try:
        if probe["status"] == "ok":
            async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
                r = await client.get(url.rstrip("/") + "/alerts?limit=1")
                if r.status_code == 200:
                    pending_alerts = int(r.json().get("total", 0))
    except Exception:
        pass

    result = {
        "status": status_label,
        "endpoint": url,
        "last_ping": datetime.now(UTC).isoformat(),
        "pending_alerts": pending_alerts,
        "recent_log": [],
        "probe": probe,
    }
    _tv_probe_cache.update({"ts": now, "result": result})
    return result


async def _tradingview_status() -> dict[str, Any]:
    """TradingView webhook pipeline status (live probe when URL is configured)."""
    status = await _probe_tradingview_webhook()
    # Also read a local log tail if the dashboard is co-located with the receiver.
    log_path_env = _env("DASHBOARD_TV_LOG", "").strip()
    if log_path_env:
        try:
            path = Path(log_path_env)
            if path.exists():
                status["recent_log"] = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-10:]
        except Exception as exc:
            log.warning("failed to read TV log %s: %s", log_path_env, exc)
    return status


async def _probe_health(name: str, url: str | None, timeout: float = 2.0) -> dict[str, Any]:
    """Probe a business health endpoint without leaking PII."""
    if not url:
        return {"name": name, "status": "not_configured", "detail": "no URL configured"}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(url)
        if r.status_code == 200:
            return {"name": name, "status": "ok", "http_status": r.status_code}
        if r.status_code in {401, 403}:
            return {"name": name, "status": "protected", "http_status": r.status_code}
        return {"name": name, "status": "degraded", "http_status": r.status_code}
    except httpx.TimeoutException:
        return {"name": name, "status": "timeout", "detail": "probe timed out"}
    except Exception as exc:
        return {"name": name, "status": "unreachable", "detail": str(exc)}


async def _business_health() -> dict[str, Any]:
    """Health grid for satellite services reachable without auth."""
    probes = [
        ("gpu_gateway", _env("GPU_GATEWAY_HEALTH_URL", "http://127.0.0.1:8800/health")),
        ("remote_gpu_gateway", _env("REMOTE_GPU_GATEWAY_HEALTH_URL", "")),
        ("ops_server", _env("OPS_SERVER_HEALTH_URL", "")),
    ]
    results = []
    for name, url in probes:
        results.append(await _probe_health(name, url or None))
    return {
        "services": results,
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def _system_health() -> dict[str, Any]:
    """High-level system health aggregates."""
    tv = await _tradingview_status()
    return {
        "dashboard": "ok",
        "gate": _gate_status()["state"],
        "telegram": _telegram_queue()["status"],
        "tradingview": tv["status"],
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Public (anonymous) view — strict whitelist. Everything not explicitly listed
# here is dropped for anonymous requests: internal URLs/hostnames, endpoint
# probes' details, proposal bodies, exact capital figures, limits/caps, file
# paths, log tails, and the authenticated username.
# ---------------------------------------------------------------------------


def _round_usd(value: Any) -> int:
    """Generalize a USD amount to the nearest $10 for the public view."""
    return int(round(_safe_float(value) / 10.0) * 10)


def _public_gate(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": gate["state"],
        "label": gate["label"],
        "armed": gate["armed"],
        "killswitch": gate["killswitch"],
        "mode": gate["mode"],
        "executor_alive": gate["executor_alive"],
        "updated_at": gate["updated_at"],
    }


def _public_wallet(wallet: dict[str, Any]) -> dict[str, Any]:
    return {
        "address": wallet["address"],  # already masked 0xabcd...1234
        "funded": bool(wallet["skin_in_game"]),
        "skin_in_game": bool(wallet["skin_in_game"]),
        "deployed_usd_approx": _round_usd(wallet["deployed_usd"]),
        "n_open": wallet["n_open"],
        "updated_at": wallet["updated_at"],
    }


def _public_telegram(queue: dict[str, Any]) -> dict[str, Any]:
    return {
        "pending": queue["pending"],
        "gate": queue["gate"],
        "status": queue["status"],
        "recent_count": queue["recent_count"],
        "proposals": [],  # proposal bodies are operator-only
    }


def _public_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": s["id"],
            "instrument": s["instrument"],
            "side": s["side"],
            "timestamp": s["timestamp"],
        }
        for s in signals
    ]


def _public_defi_report(feed: dict[str, Any]) -> dict[str, Any]:
    return {
        "clips": [
            {"id": c.get("id", ""), "title": c.get("title", ""), "source": c.get("source", ""), "path": ""}
            for c in feed.get("clips", [])
        ],
        "source": feed.get("source", ""),
        "live": bool(feed.get("live", False)),
    }


def _public_tradingview(tv: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": tv["status"],
        "last_ping": tv["last_ping"],
        "pending_alerts": tv["pending_alerts"],
    }


def _public_business_health(health: dict[str, Any]) -> dict[str, Any]:
    services = health.get("services", [])
    return {
        "services": [{"name": s.get("name", ""), "status": s.get("status", "")} for s in services],
        "ok_count": sum(1 for s in services if s.get("status") == "ok"),
        "total": len(services),
        "timestamp": health.get("timestamp", ""),
    }


def _public_system_health(health: dict[str, Any]) -> dict[str, Any]:
    return {
        "dashboard": health["dashboard"],
        "gate": health["gate"],
        "telegram": health["telegram"],
        "tradingview": health["tradingview"],
        "timestamp": health["timestamp"],
    }


@app.get("/api/v1/status")
@limiter.limit(_api_rate_limit)
async def api_status(request: Request, user: str = Depends(auth_or_public)) -> dict[str, Any]:
    gate = _gate_status()
    wallet = _wallet_status()
    system_health = await _system_health()
    if user == PUBLIC_USER:
        return {
            "service": "sapphire-alpha-dashboard",
            "version": "0.2.0",
            "public_view": True,
            "gate": _public_gate(gate),
            "wallet": _public_wallet(wallet),
            "system_health": _public_system_health(system_health),
        }
    return {
        "service": "sapphire-alpha-dashboard",
        "version": "0.2.0",
        "authenticated_user": user,
        "gate": gate,
        "wallet": wallet,
        "system_health": system_health,
    }


@app.get("/api/v1/widgets")
@limiter.limit(_api_rate_limit)
async def api_widgets(request: Request, user: str = Depends(auth_or_public)) -> dict[str, Any]:
    full = {
        "gate": _gate_status(),
        "wallet": _wallet_status(),
        "telegram_queue": _telegram_queue(),
        "recent_signals": _recent_signals(),
        "defi_report": await _defi_report_feed(),
        "tradingview": await _tradingview_status(),
        "business_health": await _business_health(),
        "system_health": await _system_health(),
        "rendered_at": datetime.now(UTC).isoformat(),
    }
    if user == PUBLIC_USER:
        return {
            "public_view": True,
            "gate": _public_gate(full["gate"]),
            "wallet": _public_wallet(full["wallet"]),
            "telegram_queue": _public_telegram(full["telegram_queue"]),
            "recent_signals": _public_signals(full["recent_signals"]),
            "defi_report": _public_defi_report(full["defi_report"]),
            "tradingview": _public_tradingview(full["tradingview"]),
            "business_health": _public_business_health(full["business_health"]),
            "system_health": _public_system_health(full["system_health"]),
            "rendered_at": full["rendered_at"],
        }
    return full


@app.get("/api/v1/tradingview/alerts")
@limiter.limit(_api_rate_limit)
async def api_tradingview_alerts(
    request: Request,
    user: str = Depends(auth_or_public),
    limit: int = 10,
    persisted: bool = True,
) -> dict[str, Any]:
    """Proxy recent TradingView webhook alerts from the Windows receiver.

    Set persisted=false to request only the receiver's in-memory window.
    Anonymous (public read-only) requests get counts only — alert payloads can
    carry strategy internals, so they are operator-only.
    """
    if user == PUBLIC_USER:
        return {"alerts": [], "total": 0, "source": "public", "public_view": True}

    url = _env("TV_WEBHOOK_URL", "").strip()
    if not url or url == "not configured":
        return {"alerts": [], "total": 0, "source": "not_configured"}

    alerts_url = url.rstrip("/") + f"/alerts?limit={max(1, min(limit, 100))}&persisted={str(persisted).lower()}"
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            r = await client.get(alerts_url)
        if r.status_code == 200:
            data = r.json()
            return {
                "alerts": data.get("alerts", []),
                "total": data.get("total", 0),
                "source": data.get("source", "webhook"),
            }
        return {"alerts": [], "total": 0, "source": "webhook", "error": f"HTTP {r.status_code}"}
    except Exception as exc:
        log.warning("failed to fetch TradingView alerts: %s", exc)
        return {"alerts": [], "total": 0, "source": "webhook", "error": str(exc)}


# ---------------------------------------------------------------------------
# Fleet snapshot (/api/fleet) — sanitized output of `fleet-lease export
# --sanitized`, pushed to FLEET_SNAPSHOT_PATH. The backend never trusts the
# file: lease/gate fields are whitelisted so a poisoned snapshot cannot leak
# paths, hints, or extra keys. Anonymous public read-only gets counts only.
# ---------------------------------------------------------------------------

_EMPTY_FLEET = {
    "generated_at": None,
    "leases": [],
    "gates": [],
    "counts": {"leases": 0, "gates_open": 0},
}


def _fleet_snapshot_path() -> Path:
    return Path(_env("FLEET_SNAPSHOT_PATH", "data/fleet.json"))


def _no_paths(value: Any) -> str:
    """Coerce to str and drop anything path-like (defense in depth)."""
    text = str(value or "")
    if "/" in text or "\\" in text:
        text = text.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return text[:120]


def _whitelist_fleet(raw: Any) -> dict[str, Any]:
    """Reduce an untrusted fleet.json to the exact serving shape."""
    if not isinstance(raw, dict):
        return dict(_EMPTY_FLEET)
    leases = [
        {
            "agent": _no_paths(lease.get("agent")),
            "repo": _no_paths(lease.get("repo")),
            "purpose": _no_paths(lease.get("purpose")),
            "expires_at": _no_paths(lease.get("expires_at")),
        }
        for lease in raw.get("leases", [])
        if isinstance(lease, dict)
    ]
    gates = [
        {
            "id": int(gate.get("id", 0)),
            "title": _no_paths(gate.get("title")),
            "age_hours": _safe_float(gate.get("age_hours")),
            "status": _no_paths(gate.get("status")),
        }
        for gate in raw.get("gates", [])
        if isinstance(gate, dict)
    ]
    generated_at = raw.get("generated_at")
    return {
        "generated_at": str(generated_at) if isinstance(generated_at, str) else None,
        "leases": leases,
        "gates": gates,
        "counts": {"leases": len(leases), "gates_open": len(gates)},
    }


def _fleet_age_seconds(generated_at: str | None) -> float | None:
    if not generated_at:
        return None
    try:
        gen = datetime.fromisoformat(generated_at)
        if gen.tzinfo is None:
            gen = gen.replace(tzinfo=UTC)
        return max(0.0, round((datetime.now(UTC) - gen).total_seconds(), 1))
    except ValueError:
        return None


@app.get("/api/fleet")
@limiter.limit(_api_rate_limit)
async def api_fleet(request: Request, user: str = Depends(auth_or_public)) -> dict[str, Any]:
    """Fleet presence (leases) + human-approval inbox (gates) with staleness."""
    snapshot = _whitelist_fleet(_read_json(_fleet_snapshot_path()))
    age_s = _fleet_age_seconds(snapshot["generated_at"])
    if user == PUBLIC_USER:
        return {
            "public_view": True,
            "leases": snapshot["counts"]["leases"],
            "gates_open": snapshot["counts"]["gates_open"],
            "snapshot_age_s": age_s,
        }
    return dict(snapshot, snapshot_age_s=age_s)


@app.get("/vault/rag-map", response_class=FileResponse)
@limiter.limit("30/minute")
async def vault_rag_map(request: Request, user: str = Depends(require_auth)) -> Response:
    """Privacy-safe Knowledge-vault RAG map (titles only, no chunk text)."""
    path = _FRONTEND_DIST_DIR / "rag-map.html"
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="rag map not built")
    return FileResponse(path, media_type="text/html")


@app.get("/assets/{filename}", response_class=FileResponse)
@limiter.limit("120/minute")
async def frontend_assets(filename: str, request: Request, user: str = Depends(auth_or_public)) -> Response:
    base = _FRONTEND_DIST_DIR / "assets"
    try:
        path = (base / filename).resolve(strict=False)
        # Prevent directory traversal outside the assets directory.
        if not path.is_relative_to(base.resolve()):
            raise HTTPException(status_code=403, detail="forbidden")
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=403, detail="forbidden")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path)


# ---------------------------------------------------------------------------
# Telegram Mini App surface (read-only; approvals stay on the bot's button rail)
# ---------------------------------------------------------------------------

_MINIAPP_HTML = Path(__file__).resolve().parent / "static" / "miniapp.html"


def tg_auth(request: Request) -> telegram_miniapp.TelegramUser:
    """Authenticate a Mini App API request via `Authorization: tma <initData>`."""
    try:
        return telegram_miniapp.authenticate_header(request.headers.get("Authorization"))
    except telegram_miniapp.InitDataError as exc:
        if str(exc) == "bot token not configured":
            raise HTTPException(status_code=503, detail="miniapp not configured") from exc
        raise HTTPException(
            status_code=401,
            detail="invalid telegram credentials",
            headers={"WWW-Authenticate": "tma"},
        ) from exc


@app.get("/miniapp", response_class=FileResponse)
@limiter.limit("60/minute")
async def miniapp_page(request: Request) -> Response:
    """Public static shell; all data behind /api/tg/* (validated initData)."""
    if not _MINIAPP_HTML.is_file():
        raise HTTPException(status_code=404, detail="miniapp not built")
    return FileResponse(_MINIAPP_HTML, media_type="text/html")


@app.get("/api/tg/summary")
@limiter.limit("60/minute")
async def api_tg_summary(
    request: Request, user: telegram_miniapp.TelegramUser = Depends(tg_auth)
) -> dict[str, Any]:
    """Operator-grade, PII-scrubbed snapshot for the Mini App (read-only)."""
    fleet = _whitelist_fleet(_read_json(_fleet_snapshot_path()))
    return {
        "viewer": {"first_name": user.first_name},
        "chain": telegram_miniapp.tag_chain({}),
        "desk": _gate_status(),
        "wallet": _wallet_status(),
        "magnum": _magnum_status(),
        "queue": _telegram_queue(),
        "signals": _recent_signals(),
        "fleet": dict(fleet, snapshot_age_s=_fleet_age_seconds(fleet["generated_at"])),
        "updated_at": datetime.now(UTC).isoformat(),
    }


@app.get("/api/tg/decisions")
@limiter.limit("60/minute")
async def api_tg_decisions(
    request: Request, user: telegram_miniapp.TelegramUser = Depends(tg_auth)
) -> dict[str, Any]:
    """Read-only decision history from decisions.jsonl (sanitized, chain-tagged)."""
    rows = _read_jsonl(_TELEGRAM_DIR / "decisions.jsonl", limit=50)
    return {
        "decisions": [telegram_miniapp.sanitize_decision(r, i + 1) for i, r in enumerate(rows)],
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# Public marketing site (statically exported Next.js) + operator dashboard.
#
# Route order matters: FastAPI matches in declaration order and the catch-all
# below swallows everything, so every specific route must be declared above it.
# ---------------------------------------------------------------------------


@app.get("/_next/{path:path}", response_class=FileResponse)
@limiter.limit("240/minute")
async def web_next_assets(path: str, request: Request) -> Response:
    """Fingerprinted Next.js build assets. Public, immutable, no auth."""
    resolved = _resolve_static(_WEB_OUT_DIR / "_next", path)
    if resolved is None:
        raise HTTPException(status_code=404, detail="not found")
    return _static_file_response(resolved, _IMMUTABLE_CACHE)


def _dashboard_index() -> Response:
    """Serve the operator SPA shell.

    Vite emits absolute asset URLs (`/assets/...`), so the bundle works unchanged
    from this path — only the entry point moved off `/`.
    """
    index = _FRONTEND_DIST_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="frontend bundle not built")
    return _static_file_response(index, _MARKETING_CACHE)


@app.get("/dashboard", response_class=FileResponse)
@limiter.limit("60/minute")
async def dashboard_root(request: Request, user: str = Depends(auth_or_public)) -> Response:
    return _dashboard_index()


@app.get("/dashboard/{path:path}", response_class=FileResponse)
@limiter.limit("60/minute")
async def dashboard_spa(path: str, request: Request, user: str = Depends(auth_or_public)) -> Response:
    return _dashboard_index()


@app.get("/{catchall:path}", response_class=FileResponse)
@limiter.limit("60/minute")
async def frontend_root(catchall: str, request: Request) -> Response:
    """Serve the public marketing site.

    Anonymous by design: this is the front door, and gating it behind Basic auth
    would make the site unreachable whenever PUBLIC_READ_ONLY is off. It serves
    only statically exported marketing content — no operator state reaches here.

    Falls back to the dashboard shell when `web/out` is absent, so a backend-only
    checkout still renders something rather than 503-ing.
    """
    resolved = _resolve_static(_WEB_OUT_DIR, catchall)
    if resolved is not None:
        return _static_file_response(resolved, _MARKETING_CACHE)

    if not _WEB_OUT_DIR.is_dir():
        return _dashboard_index()

    # Marketing site is built but this path is not one of its routes.
    not_found = _resolve_static(_WEB_OUT_DIR, "404")
    if not_found is not None:
        return FileResponse(
            not_found,
            status_code=404,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": _MARKETING_CACHE},
        )
    raise HTTPException(status_code=404, detail="not found")


@app.exception_handler(Exception)
async def _generic_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "internal error"},
    )

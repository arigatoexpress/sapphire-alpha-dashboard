"""
Sapphire Alpha Dashboard — Mission Control.

Public endpoints:
  GET /healthz
  GET /api/health

Authenticated endpoints (HTTP Basic Auth):
  GET /api/v1/status
  GET /api/v1/widgets
  GET /api/v1/transparency

Anonymous read access:
  Every GET is anonymous. /api/v1/live is served un-redacted — the real
  latencies, event rates and freshness, identical to what an operator sees.
  The remaining sanitizers are narrow and deliberate, not a general tier:
  /api/v1/status, /api/v1/widgets, /api/v1/fleet and /api/v1/tradingview/alerts
  still drop internal URLs/hostnames, proposal bodies, exact capital figures,
  limits/caps and file paths for anonymous callers, and /api/v1/moss keeps
  capital in bands (Ari, 2026-07-25). Authenticated users get the full payload.

  Reads being public does not make writes public: methods other than GET/HEAD require auth,
  signed ingest keeps its HMAC, and /vault/rag-map always requires auth.
"""

from __future__ import annotations

import html
import hashlib
import json
import logging
import os
import re
import secrets
import stat
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
    from . import public_vault_map, transparency
    from .live_telemetry import TelemetryValidationError, store as live_telemetry_store
    from .moss_telemetry import MossTelemetryValidationError, store as moss_telemetry_store
except ImportError:  # Tests import `main` directly from backend/.
    import public_vault_map
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


def _api_rate_limit() -> str:
    """Rate limit for API routes.

    Anonymous reads are unconditional now, so the tighter of the two former
    limits is the only one that applies; there is no operator-only mode left in
    which the looser 60/minute would have been correct.
    """
    return "20/minute"


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
_KNOWLEDGE_ROOT = Path(_env("KNOWLEDGE_ROOT", str(Path.home() / "Knowledge")))

# Statically exported Next.js marketing site (`web/`). Served from this same
# container so the public site, the operator dashboard, and the API share one
# Cloud Run service and one domain.
_WEB_OUT_DIR = Path(__file__).resolve().parent.parent / "web" / "out"


def _sha256_file(path: Path) -> str | None:
    """Hash one shipped entrypoint without disclosing its filesystem path."""
    try:
        with path.open("rb") as handle:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
            return digest.hexdigest()
    except OSError:
        return None


def _surface_manifest(root: Path, entrypoint_url: str) -> dict[str, Any]:
    """Digest every regular file served for one frontend without listing paths."""
    entrypoint_sha256 = _sha256_file(root / "index.html")
    entries: list[str] = []
    try:
        base = root.resolve(strict=True)
    except OSError:
        base = None

    if base is not None and base.is_dir():
        for candidate in sorted(base.rglob("*")):
            if candidate.is_symlink():
                continue
            try:
                resolved = candidate.resolve(strict=True)
            except OSError:
                continue
            if not resolved.is_relative_to(base) or not resolved.is_file():
                continue
            try:
                size = resolved.stat().st_size
            except OSError:
                continue
            digest = _sha256_file(resolved)
            if digest is None:
                continue
            relative = resolved.relative_to(base).as_posix()
            entries.append(f"{relative}\0{size}\0{digest}\n")

    manifest_sha256 = (
        hashlib.sha256("".join(entries).encode("utf-8")).hexdigest() if entries else None
    )
    return {
        "entrypoint_url": entrypoint_url,
        "entrypoint_sha256": entrypoint_sha256,
        "asset_count": len(entries),
        "manifest_sha256": manifest_sha256,
    }


def _identity_value(name: str, default: str) -> str:
    """Return a bounded public-safe build label, never arbitrary env content."""
    value = _env(name, default)
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value):
        return value
    return default


@lru_cache(maxsize=1)
def _build_identity() -> dict[str, Any]:
    """Bind source, build, runtime revision, and the two served entrypoints."""
    source_sha = _identity_value("SAPPHIRE_BUILD_SHA", "unknown").lower()
    if not re.fullmatch(r"[0-9a-f]{40,64}", source_sha):
        source_sha = "unknown"

    build_id = _identity_value("SAPPHIRE_BUILD_ID", "unknown")
    runtime_service = _identity_value("K_SERVICE", "local")
    runtime_revision = _identity_value("K_REVISION", "local")
    surfaces = {
        "operator": _surface_manifest(_FRONTEND_DIST_DIR, "/dashboard"),
        "public": _surface_manifest(_WEB_OUT_DIR, "/"),
    }
    complete = (
        source_sha != "unknown"
        and build_id != "unknown"
        and runtime_revision != "local"
        and all(
            surface["entrypoint_sha256"]
            and surface["asset_count"]
            and surface["manifest_sha256"]
            for surface in surfaces.values()
        )
    )
    return {
        "schema": 1,
        "source_sha": source_sha,
        "build_id": build_id,
        "runtime_service": runtime_service,
        "runtime_revision": runtime_revision,
        "surfaces": surfaces,
        "complete": complete,
    }


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
_OBSERVATIONS_DIR = _HOME / "ops-state" / "sapphire-observations"
_PAUSE_SENTINELS: dict[str, Path] = {
    "mac": _HOME / ".sapphire" / "autonomous_trading_pause",
    "rh_chain": _RH_CHAIN_DIR / "killswitch",
}
_RUNTIME_TTL_SECONDS = 180.0
_MAX_PAUSE_DOCUMENT_BYTES = 64 * 1024
_MAX_LOCAL_TELEMETRY_DOCUMENT_BYTES = 256 * 1024
_MAX_FLEET_FUTURE_SKEW_SECONDS = 5.0

_RUNTIME_READINESS: dict[str, Any] = {
    "schema_version": "sapphire-runtime-readiness/v1",
    "task063": {
        "status": "SOURCE_MERGED_INERT",
        "merged_commit": "4205e79ac53e56b03949bf266f2a3b074a651d71",
    },
    "task065": {
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
    },
    "credential_enrollment": "UNAVAILABLE",
    "broker_reconciliation": "UNAVAILABLE",
    "runtime_installation": "UNAVAILABLE",
    "production_execution": "UNAVAILABLE",
}


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
    """Anonymous GET/HEAD reads are allowed; every mutating method requires auth.

    Reads are public because the system is meant to be watched — that is the
    whole point of the machine room. Writes are a different question and the
    answer did not change: un-redacting reads must not un-protect writes, so
    mutating methods still require credentials, and signed ingest keeps its HMAC
    regardless of this dependency.

    Presented credentials are always validated, so bad credentials never fall
    back to the anonymous path.
    """
    if credentials is not None:
        return require_auth(credentials)
    if request.method in {"GET", "HEAD"}:
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


@app.get("/api/v1/readiness")
@limiter.limit("30/minute")
async def api_runtime_readiness(request: Request) -> dict[str, Any]:
    """Source/dependency readiness; this endpoint grants no runtime authority."""
    return _readiness_snapshot()


def _readiness_snapshot() -> dict[str, Any]:
    """Return an isolated copy of the inert source/dependency receipt."""
    return json.loads(json.dumps(_RUNTIME_READINESS))


@app.get("/api/build")
@limiter.limit("30/minute")
async def api_build(request: Request, response: Response) -> dict[str, Any]:
    """Public, sanitized proof of the source and frontend bytes in this process."""
    response.headers["Cache-Control"] = "no-store"
    return _build_identity()


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
async def api_live(
    request: Request,
    response: Response,
    user: str = Depends(auth_or_public),
) -> dict[str, Any]:
    """Serve the current snapshot — the same one, undelayed, to every reader."""
    response.headers["Cache-Control"] = "no-store"
    return live_telemetry_store.get(public=user == PUBLIC_USER)


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
    """Serve exact operator detail or a banded anonymous MOSS projection.

    Capital is the one thing that stays redacted (Ari, 2026-07-25) — but it is
    redacted by *banding*, not by delay. The delay knob survives here only for
    MOSS; it now defaults to 0 so the code agrees with the deployed config
    instead of relying on an env var to switch off a behaviour nobody wants.
    """
    public = user == PUBLIC_USER
    try:
        delay_seconds = max(0.0, min(300.0, float(_env("PUBLIC_TELEMETRY_DELAY_SECONDS", "0"))))
    except ValueError:
        delay_seconds = 0.0
    return moss_telemetry_store.get(public=public, delay_seconds=delay_seconds)


@app.get("/api/v1/transparency")
@limiter.limit(_api_rate_limit)
async def api_transparency(
    request: Request, user: str = Depends(auth_or_public)
) -> dict[str, Any]:
    """Explanation-ledger pane: operator full detail or sanitized public bands."""
    public = user == PUBLIC_USER
    ledger = Path(_env("DASHBOARD_EXPLANATIONS_PATH", "")
                  or (_OBSERVATIONS_DIR / transparency.LEDGER_NAME))
    return transparency.snapshot(ledger, public=public)


def _read_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("failed to read %s: %s", path, exc)
    return None


def _persisted_time(value: Any) -> datetime | None:
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            parsed = datetime.fromtimestamp(float(value), UTC)
        elif isinstance(value, str) and value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            return None
    except (ValueError, OSError, OverflowError):
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def _observation_time(data: dict[str, Any]) -> datetime | None:
    for key in ("observed_at", "updated_at", "updated", "last_seen", "timestamp", "epoch"):
        if (parsed := _persisted_time(data.get(key))) is not None:
            return parsed
    return None


def _executor_heartbeat(*, now: datetime | None = None) -> dict[str, Any]:
    """Executor liveness from one persisted heartbeat; absence stays unknown."""
    now = now or datetime.now(UTC)
    data = _read_json(_RH_CHAIN_DIR / "executor-heartbeat.json")
    if not isinstance(data, dict):
        return {"status": "unknown", "alive": None, "last_seen": None, "pid": None}

    observed = _observation_time(data)
    current = (
        observed is not None
        and 0 <= (now - observed).total_seconds() <= _RUNTIME_TTL_SECONDS
    )
    status_str = str(data.get("status", "unknown")).lower()
    reported_alive = status_str in {"alive", "ok", "running", "healthy"} or (
        data.get("alive") is True
    )
    return {
        "status": status_str if current else "unknown",
        "alive": reported_alive if current else None,
        "last_seen": observed.isoformat() if observed is not None else None,
        "pid": data.get("pid") if current else None,
    }


def _skin_book() -> dict[str, Any]:
    """Read only a persisted skin-book observation."""
    data = _read_json(_RH_CHAIN_DIR / "skin-book.json")
    if not isinstance(data, dict):
        data = {}

    positions = data.get("positions", [])
    fills = data.get("fills", [])
    observed = _observation_time(data)
    return {
        "updated_at": observed.isoformat() if observed is not None else None,
        "mode": data.get("mode") or "unavailable",
        "banner": data.get("banner", "Skin book"),
        "deployed_usd": _safe_float(data.get("deployed_usd")),
        "n_open": int(data.get("n_open", len(positions))),
        "positions_count": len(positions),
        "fills_count": len(fills),
        "skin_in_game": (
            data.get("skin_in_game")
            if isinstance(data.get("skin_in_game"), bool)
            else None
        ),
        "limits": data.get("limits", {}),
    }


def _invalid_pause_observation(source: str) -> dict[str, Any]:
    return {"source": source, "state": "invalid", "observed_at": None}


def _open_pause_parent(directory: Path) -> int:
    """Open an absolute directory one non-symlink component at a time."""
    if not directory.is_absolute() or any(
        component in {"", ".", ".."} for component in directory.parts[1:]
    ):
        raise OSError("pause parent must be an absolute normalized path")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    current = os.open(os.sep, flags)
    try:
        for component in directory.parts[1:]:
            next_fd = os.open(component, flags, dir_fd=current)
            os.close(current)
            current = next_fd
        return current
    except Exception:
        os.close(current)
        raise


def _stable_stat_identity(value: os.stat_result) -> tuple[int, ...]:
    """Fields whose drift makes one persisted read unverifiable."""
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


class _UnverifiablePersistedDocument(ValueError):
    """A local document could not be bound to one stable admitted descriptor."""


def _read_admitted_json_object(
    path: Path,
    *,
    max_bytes: int,
) -> tuple[dict[str, Any], tuple[int, int]] | None:
    """Read one bounded local JSON object through a stable no-follow descriptor."""
    parent_fd: int | None = None
    file_fd: int | None = None
    fresh_parent_fd: int | None = None
    try:
        parent_fd = _open_pause_parent(path.parent)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise _UnverifiablePersistedDocument from exc

    try:
        parent_before = os.fstat(parent_fd)
        if (
            not stat.S_ISDIR(parent_before.st_mode)
            or parent_before.st_uid != os.geteuid()
            or parent_before.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise _UnverifiablePersistedDocument

        flags = os.O_RDONLY
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_NONBLOCK", 0)
        try:
            file_fd = os.open(path.name, flags, dir_fd=parent_fd)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise _UnverifiablePersistedDocument from exc

        before = os.fstat(file_fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            or before.st_nlink != 1
            or before.st_size > max_bytes
        ):
            raise _UnverifiablePersistedDocument

        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(file_fd, min(8192, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(file_fd)
        parent_after = os.fstat(parent_fd)
        try:
            path_after = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            fresh_parent_fd = _open_pause_parent(path.parent)
            fresh_parent = os.fstat(fresh_parent_fd)
            fresh_path = os.stat(
                path.name,
                dir_fd=fresh_parent_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise _UnverifiablePersistedDocument from exc
        stable_descriptor = _stable_stat_identity(before) == _stable_stat_identity(after)
        stable_parent = (
            _stable_stat_identity(parent_before)
            == _stable_stat_identity(parent_after)
            == _stable_stat_identity(fresh_parent)
        )
        same_path_object = (
            stat.S_ISREG(path_after.st_mode)
            and stat.S_ISREG(fresh_path.st_mode)
            and _stable_stat_identity(after)
            == _stable_stat_identity(path_after)
            == _stable_stat_identity(fresh_path)
        )
        if (
            not stable_descriptor
            or not stable_parent
            or not same_path_object
            or len(payload) != after.st_size
            or len(payload) > max_bytes
        ):
            raise _UnverifiablePersistedDocument

        raw = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
        )
        if not isinstance(raw, dict):
            raise _UnverifiablePersistedDocument
        return raw, (after.st_dev, after.st_ino)
    except _UnverifiablePersistedDocument:
        raise
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise _UnverifiablePersistedDocument from exc
    finally:
        if fresh_parent_fd is not None:
            os.close(fresh_parent_fd)
        if file_fd is not None:
            os.close(file_fd)
        if parent_fd is not None:
            os.close(parent_fd)


_PAUSE_TIMESTAMP_FIELDS = frozenset(
    {
        "observed_at",
        "updated_at",
        "updated",
        "last_seen",
        "timestamp",
        "epoch",
        "created_at",
    }
)


def _strict_pause_semantics(raw: dict[str, Any]) -> tuple[str, datetime] | None:
    """Accept one explicit timestamp schema plus the legacy active sentinel."""
    present_timestamps = _PAUSE_TIMESTAMP_FIELDS.intersection(raw)
    if "state" not in raw:
        if present_timestamps != {"created_at"}:
            return None
        state = "active"
        observed = _persisted_time(raw.get("created_at"))
    else:
        state = raw.get("state")
        if state not in {"active", "clear"} or present_timestamps != {"observed_at"}:
            return None
        observed = _persisted_time(raw.get("observed_at"))
    return (state, observed) if observed is not None else None


def _pause_file_observation(source: str, path: Path) -> dict[str, Any] | None:
    """Read one pause sentinel through the shared admitted-document contract."""
    try:
        admitted = _read_admitted_json_object(
            path,
            max_bytes=_MAX_PAUSE_DOCUMENT_BYTES,
        )
    except _UnverifiablePersistedDocument:
        return _invalid_pause_observation(source)
    if admitted is None:
        return None
    raw, source_identity = admitted
    semantics = _strict_pause_semantics(raw)
    if semantics is None:
        return _invalid_pause_observation(source)
    state, observed = semantics
    return {
        "source": source,
        "state": state,
        "observed_at": observed.isoformat(),
        "_source_identity": source_identity,
    }


def _evaluate_pause_truth(
    observations: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve two persisted pause sources without treating absence as clear."""
    now = now or datetime.now(UTC)
    states: dict[str, set[str]] = {"mac": set(), "rh_chain": set()}
    observed_times: list[datetime] = []
    clear_is_current = True
    invalid = False
    source_identities: set[tuple[int, int]] = set()
    for item in observations:
        if not isinstance(item, dict):
            invalid = True
            continue
        source = item.get("source")
        state = item.get("state")
        observed = _persisted_time(item.get("observed_at"))
        identity = item.get("_source_identity")
        if source not in states or state not in {"active", "clear"} or observed is None:
            invalid = True
            continue
        if (
            not isinstance(identity, (list, tuple))
            or len(identity) != 2
            or any(type(value) is not int for value in identity)
        ):
            invalid = True
            continue
        normalized_identity = (identity[0], identity[1])
        if normalized_identity in source_identities:
            invalid = True
            continue
        source_identities.add(normalized_identity)
        states[source].add(state)
        observed_times.append(observed)
        if state == "clear":
            age = (now - observed).total_seconds()
            clear_is_current = clear_is_current and 0 <= age <= _RUNTIME_TTL_SECONDS

    if invalid or any(len(values) != 1 for values in states.values()):
        state = "unknown"
    elif any("active" in values for values in states.values()):
        state = "active"
    elif clear_is_current:
        state = "clear"
    else:
        state = "unknown"
    return {
        "state": state,
        "clear": True if state == "clear" else False if state == "active" else None,
        "observed_at": (
            min(observed_times).isoformat() if observed_times else None
        ),
    }


def _gate_status(*, now: datetime | None = None) -> dict[str, Any]:
    """Project one persisted gate and two fail-closed pause observations."""
    now = now or datetime.now(UTC)
    raw_gate = _read_json(_RH_CHAIN_DIR / "gate.json")
    gate = raw_gate if isinstance(raw_gate, dict) else {}
    observations: list[dict[str, Any]] = []
    for source, path in _PAUSE_SENTINELS.items():
        if (item := _pause_file_observation(source, path)) is not None:
            observations.append(item)
    pause = _evaluate_pause_truth(observations, now=now)

    gate_observed = _observation_time(gate)
    gate_current = (
        gate_observed is not None
        and 0 <= (now - gate_observed).total_seconds() <= _RUNTIME_TTL_SECONDS
    )
    reported_mode = gate.get("mode")
    mode = (
        reported_mode
        if gate_current and reported_mode in {"bounded_auto", "manual", "off"}
        else "unavailable"
    )

    if pause["state"] == "active":
        state, label, armed, killswitch = "paused", "Pause active", False, True
    elif pause["state"] != "clear" or not gate_current:
        state, label, armed, killswitch = (
            "unavailable",
            "Pause state unavailable",
            None,
            None,
        )
        mode = "unavailable"
    else:
        armed = gate.get("armed") if isinstance(gate.get("armed"), bool) else None
        killswitch = False
        if armed is None or mode == "unavailable":
            state, label = "unavailable", "Gate state unavailable"
        elif armed:
            state, label = "armed", "Bounded gate armed"
        else:
            state, label = "disarmed", "Gate disarmed"

    wallet_addr = gate.get("wallet_address")
    return {
        "state": state,
        "label": label,
        "armed": armed,
        "killswitch": killswitch,
        "pause_state": pause["state"],
        "mode": mode,
        "wallet_address": _mask_address(wallet_addr),
        "cap_usd": gate.get("cap_usd") if gate_current else None,
        "executor_alive": _executor_heartbeat(now=now)["alive"],
        "updated_at": gate_observed.isoformat() if gate_observed is not None else None,
    }


def _wallet_status() -> dict[str, Any]:
    """Privacy-preserving wallet / PnL tile."""
    skin = _skin_book()
    raw = _read_json(_RH_CHAIN_DIR / "skin-book.json")
    wallet_addr = raw.get("wallet_address") if isinstance(raw, dict) else None
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


def _recent_signals() -> list[dict[str, Any]]:
    """Recent observed trading signals with synthetic display identifiers."""
    data = _read_json(_RH_CHAIN_DIR / "signals.json")

    if isinstance(data, list):
        return [
            {
                "id": f"sig-{i+1:03d}",
                "instrument": s.get("instrument", "UNKNOWN"),
                "side": s.get("side", "-"),
                "venue": s.get("venue", "manual"),
                "confidence": s.get("confidence", "medium"),
                "timestamp": s.get("timestamp"),
            }
            for i, s in enumerate(data[:12])
        ]
    # Missing observations must stay visibly empty; production never fabricates alpha.
    return []


_RESEARCH_POLICY: dict[str, Any] = {
    "owner": {
        "id": "ari",
        "label": "Ari's investment thesis",
        "role": "mandate",
    },
    "cycle_prior": {
        "as_of": "2026-07-25",
        "posture": "late_cycle_capital_preservation",
        "primary_lens": "benjamin_cowen",
    },
    "rules": {
        "analysts_are_advisory_only": True,
        "single_analyst_evidence_cap": 0.25,
        "minimum_independent_primary_sources": 2,
        "analyst_can_set_conviction": False,
        "analyst_can_authorize_execution": False,
    },
    "lenses": {
        "benjamin_cowen": {
            "label": "Benjamin Cowen",
            "domain": "cycle and risk",
            "scope": "primary_cycle_lens",
        },
        "arthur_hayes": {
            "label": "Arthur Hayes",
            "domain": "macro liquidity",
            "scope": "scenario_and_countercase",
        },
        "bankless": {
            "label": "Bankless",
            "domain": "crypto market structure",
            "scope": "structural_theme_discovery",
        },
        "limitless": {
            "label": "Limitless",
            "domain": "AI and frontier technology",
            "scope": "technology_theme_discovery",
        },
        "michael_nadeau": {
            "label": "Michael Nadeau",
            "domain": "fundamentals and value accrual",
            "scope": "fundamentals_only",
        },
    },
}

_MAX_RESEARCH_CLIPS = 10
_MAX_CLIPS_PER_SOURCE = 2


def _clean_research_text(value: Any, *, fallback: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text[:240] or fallback


def _research_feed() -> dict[str, Any]:
    """Return an explicit, balanced research feed with no fabricated fallback.

    Producers provide reviewed clips through ``DASHBOARD_RESEARCH_CLIPS_JSON``.
    Unknown sources are rejected and no source may occupy more than two slots.
    The clips remain advisory: the policy shipped beside them makes clear that
    Ari's checked-in thesis owns conviction and a separate gate owns execution.
    """

    raw = _env("DASHBOARD_RESEARCH_CLIPS_JSON", "").strip()
    parsed: Any = []
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("DASHBOARD_RESEARCH_CLIPS_JSON is not valid JSON")

    clips: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    if isinstance(parsed, list):
        for index, item in enumerate(parsed):
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or "").strip()
            if source not in _RESEARCH_POLICY["lenses"]:
                continue
            if source_counts.get(source, 0) >= _MAX_CLIPS_PER_SOURCE:
                continue
            title = _clean_research_text(item.get("title"), fallback="Untitled research note")
            raw_id = str(item.get("id") or title).lower()
            clip_id = re.sub(r"[^a-z0-9]+", "-", raw_id).strip("-")[:80]
            clips.append(
                {
                    "id": clip_id or f"research-{index + 1:03d}",
                    "title": title,
                    "source": source,
                    "path": str(item.get("path") or ""),
                    "observed_at": str(item.get("observed_at") or ""),
                }
            )
            source_counts[source] = source_counts.get(source, 0) + 1
            if len(clips) >= _MAX_RESEARCH_CLIPS:
                break

    # A fixed item limit is not an evidence-share cap: two clips from one
    # analyst would still dominate a three-item feed. Trim the newest clip from
    # any overrepresented source until every remaining source is at or below
    # the policy share. With analyst clips alone this conservatively requires
    # at least four independent voices.
    cap = float(_RESEARCH_POLICY["rules"]["single_analyst_evidence_cap"])
    while clips:
        final_counts = {
            source: sum(1 for clip in clips if clip["source"] == source)
            for source in {clip["source"] for clip in clips}
        }
        overrepresented = {
            source for source, count in final_counts.items() if count / len(clips) > cap
        }
        if not overrepresented:
            break
        drop_index = next(
            index
            for index in range(len(clips) - 1, -1, -1)
            if clips[index]["source"] in overrepresented
        )
        clips.pop(drop_index)

    source_counts = {
        source: sum(1 for clip in clips if clip["source"] == source)
        for source in {clip["source"] for clip in clips}
    }
    return {
        "clips": clips,
        "sources_observed": sorted(source_counts),
        "live": bool(clips),
        "policy": _RESEARCH_POLICY,
    }


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
            "last_ping": None,
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
    last_ping: str | None = None
    try:
        if probe["status"] == "ok":
            async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
                r = await client.get(url.rstrip("/") + "/alerts?limit=1")
                if r.status_code == 200:
                    payload = r.json()
                    pending_alerts = int(payload.get("total", 0))
                    alerts = payload.get("alerts")
                    if isinstance(alerts, list) and alerts and isinstance(alerts[0], dict):
                        observed = _observation_time(alerts[0])
                        last_ping = observed.isoformat() if observed is not None else None
    except Exception:
        pass

    result = {
        "status": status_label,
        "endpoint": url,
        "last_ping": last_ping,
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
        "tradingview": tv["status"],
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Public (anonymous) view — strict whitelist. Everything not explicitly listed
# here is dropped for anonymous requests: internal URLs/hostnames, endpoint
# probes' details, proposal bodies, exact capital figures, limits/caps, file
# paths, log tails, and the authenticated username.
# ---------------------------------------------------------------------------


def _public_gate(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": gate["state"],
        "label": gate["label"],
        "armed": gate["armed"],
        "killswitch": gate["killswitch"],
        "pause_state": gate["pause_state"],
        "mode": gate["mode"],
        "executor_alive": gate["executor_alive"],
        "updated_at": gate["updated_at"],
    }


def _public_wallet(_wallet: dict[str, Any]) -> dict[str, Any]:
    return {"disclosure": "withheld"}


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


def _public_research(feed: dict[str, Any]) -> dict[str, Any]:
    rules = _RESEARCH_POLICY["rules"]
    return {
        "clips": [
            {
                "id": c.get("id", ""),
                "title": c.get("title", ""),
                "observed_at": c.get("observed_at", ""),
            }
            for c in feed.get("clips", [])
        ],
        "live": bool(feed.get("live", False)),
        "policy": {
            "research_role": "evidence_not_authority",
            "single_input_cap": rules["single_analyst_evidence_cap"],
            "minimum_independent_checks": rules["minimum_independent_primary_sources"],
            "can_set_conviction": rules["analyst_can_set_conviction"],
            "can_authorize_execution": rules["analyst_can_authorize_execution"],
        },
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
        "recent_signals": _recent_signals(),
        "research": _research_feed(),
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
            "recent_signals": _public_signals(full["recent_signals"]),
            "research": _public_research(full["research"]),
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
    "counts": {"leases": None, "gates_open": None},
}


def _fleet_snapshot_path() -> Path:
    return Path(_env("FLEET_SNAPSHOT_PATH", "data/fleet.json"))


def _no_paths(value: Any) -> str:
    """Coerce to str and drop anything path-like (defense in depth)."""
    text = str(value or "")
    if "/" in text or "\\" in text:
        text = text.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return text[:120]


def _whitelist_fleet(
    raw: Any,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Reduce an untrusted fleet.json to the exact serving shape."""
    if not isinstance(raw, dict):
        return dict(_EMPTY_FLEET)
    generated_at = raw.get("generated_at")
    age_s = _fleet_age_seconds(generated_at, now=now)
    if not isinstance(generated_at, str) or age_s is None:
        return dict(_EMPTY_FLEET)
    if age_s > _RUNTIME_TTL_SECONDS:
        return {
            "generated_at": generated_at,
            "leases": [],
            "gates": [],
            "counts": {"leases": None, "gates_open": None},
        }
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
    return {
        "generated_at": generated_at,
        "leases": leases,
        "gates": gates,
        "counts": {"leases": len(leases), "gates_open": len(gates)},
    }


def _fleet_age_seconds(
    generated_at: str | None,
    *,
    now: datetime | None = None,
) -> float | None:
    if not generated_at:
        return None
    try:
        gen = datetime.fromisoformat(generated_at)
        if gen.tzinfo is None:
            gen = gen.replace(tzinfo=UTC)
        observed_now = now or datetime.now(UTC)
        delta = (observed_now - gen).total_seconds()
        if delta < -_MAX_FLEET_FUTURE_SKEW_SECONDS:
            return None
        return round(max(0.0, delta), 1)
    except (TypeError, ValueError):
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


@app.get("/api/v1/vault-map")
@limiter.limit(_api_rate_limit)
async def api_public_vault_map(
    request: Request, _user: str = Depends(auth_or_public)
) -> dict[str, Any]:
    """Fixed public topic graph with aggregate counts and no vault-derived text."""
    return public_vault_map.generate(_KNOWLEDGE_ROOT)


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


@app.head("/_next/{path:path}", response_class=FileResponse)
@limiter.limit("240/minute")
async def web_next_assets_head(path: str, request: Request) -> Response:
    return await web_next_assets(path, request)


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


@app.head("/dashboard", response_class=FileResponse)
@limiter.limit("60/minute")
async def dashboard_root_head(
    request: Request, user: str = Depends(auth_or_public)
) -> Response:
    return _dashboard_index()


@app.head("/dashboard/{path:path}", response_class=FileResponse)
@limiter.limit("60/minute")
async def dashboard_spa_head(
    path: str, request: Request, user: str = Depends(auth_or_public)
) -> Response:
    return _dashboard_index()


def _marketing_response(catchall: str) -> Response:
    """Resolve one statically exported marketing path.

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


@app.get("/{catchall:path}", response_class=FileResponse)
@limiter.limit("60/minute")
async def frontend_root(catchall: str, request: Request) -> Response:
    return _marketing_response(catchall)


@app.head("/{catchall:path}", response_class=FileResponse)
@limiter.limit("60/minute")
async def frontend_head(catchall: str, request: Request) -> Response:
    """Let static-export prefetchers and crawlers verify pages without 405s."""
    return _marketing_response(catchall)


@app.exception_handler(Exception)
async def _generic_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "internal error"},
    )

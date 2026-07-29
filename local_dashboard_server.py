#!/usr/bin/env python3
"""Local offline fallback for the Sapphire Alpha dashboard.

Serves the built frontend assets from `frontend/dist` and mirrors the public
`/api/v1/live` endpoint from one separately persisted, admitted snapshot.

No cloud credentials, secrets, network push, or request-time collection are
required. Missing or unverifiable persisted evidence stays offline.

Usage:
    python local_dashboard_server.py --port 8080
    open http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from datetime import UTC, datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

# Make the backend package importable without installing it.
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from live_telemetry import (  # type: ignore[import]  # noqa: E402
    DEFAULT_STALE_AFTER_SECONDS,
    _age_runtime_projection,
    _empty_snapshot,
    validate_snapshot,
)
from main import (  # type: ignore[import]  # noqa: E402
    _MAX_LOCAL_TELEMETRY_DOCUMENT_BYTES,
    _UnverifiablePersistedDocument,
    _build_identity as _runtime_build_identity,
    _read_admitted_json_object,
    _readiness_snapshot as _runtime_readiness,
)


FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
DEFAULT_PORT = 8080
DEFAULT_LOCAL_TELEMETRY_SNAPSHOT = (
    Path.home() / "ops-state" / "sapphire-observations" / "live-snapshot.json"
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _local_snapshot_path() -> Path:
    configured = os.getenv("SAPPHIRE_LOCAL_TELEMETRY_SNAPSHOT", "").strip()
    return Path(configured) if configured else DEFAULT_LOCAL_TELEMETRY_SNAPSHOT


def _offline_live_snapshot(*, now: float) -> dict[str, Any]:
    projected = _empty_snapshot(status="offline")
    projected["served_at"] = datetime.fromtimestamp(now, UTC).isoformat()
    return projected


def _build_live_snapshot(
    *,
    snapshot_path: Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Load, age, and project one admitted persisted local snapshot."""
    now = time.time() if now is None else now
    source = snapshot_path or _local_snapshot_path()
    try:
        admitted = _read_admitted_json_object(
            source,
            max_bytes=_MAX_LOCAL_TELEMETRY_DOCUMENT_BYTES,
        )
    except _UnverifiablePersistedDocument:
        return _offline_live_snapshot(now=now)
    if admitted is None:
        return _offline_live_snapshot(now=now)
    raw, _source_identity = admitted
    try:
        projected = validate_snapshot(raw)
        observed = datetime.fromisoformat(projected["observed_at"]).timestamp()
    except (RecursionError, TypeError, ValueError):
        return _offline_live_snapshot(now=now)
    if observed > now:
        return _offline_live_snapshot(now=now)
    freshness_s = round(max(0.0, now - observed), 1)
    _age_runtime_projection(
        projected,
        now=now,
        snapshot_observed_at=observed,
        stale_after_seconds=DEFAULT_STALE_AFTER_SECONDS,
    )
    projected.update(
        {
            "status": (
                "live" if freshness_s <= DEFAULT_STALE_AFTER_SECONDS else "stale"
            ),
            "freshness_s": freshness_s,
            "served_at": datetime.fromtimestamp(now, UTC).isoformat(),
            "received_at": projected["observed_at"],
        }
    )
    return projected


def _empty_moss_snapshot() -> dict[str, Any]:
    return {
        "version": 1,
        "status": "offline",
        "observed_at": None,
        "freshness_s": None,
        "served_at": _utc_now(),
        "public_view": True,
        "network": "MegaETH",
        "asset": "MOSS",
        "usdm_band": "not observed",
        "eth_state": "not observed",
        "observation_freshness": "not observed",
        "custody": "passkey",
        "authority": "read-only",
    }


def _empty_fleet_counts() -> dict[str, Any]:
    return {
        "public_view": True,
        "leases": None,
        "gates_open": None,
        "snapshot_age_s": None,
    }


def _empty_widgets() -> dict[str, Any]:
    """Return the complete, fail-closed watchboard contract while offline."""
    rendered_at = _utc_now()
    return {
        "gate": {
            "state": "unavailable",
            "label": "Pause state unavailable",
            "armed": None,
            "killswitch": None,
            "pause_state": "unknown",
            "mode": "unavailable",
            "executor_alive": None,
            "updated_at": None,
        },
        "wallet": {"disclosure": "withheld"},
        "recent_signals": [],
        "research": {
            "clips": [],
            "live": False,
            "policy": {
                "research_role": "unverified_advisory_input",
                "single_input_cap": 0.25,
                "minimum_distinct_inputs": 4,
                "review_status": "unverified",
                "primary_source_provenance": "not_attested",
                "can_set_conviction": False,
                "can_authorize_execution": False,
            },
        },
        "tradingview": {
            "status": "not_observed",
            "last_ping": None,
            "pending_alerts": None,
        },
        "business_health": {
            "services": [
                {"name": "gpu_gateway", "status": "not_observed"},
                {"name": "remote_gpu_gateway", "status": "not_observed"},
                {"name": "ops_server", "status": "not_observed"},
            ],
            "ok_count": 0,
            "total": 3,
            "timestamp": rendered_at,
        },
        "system_health": {
            "dashboard": "ok",
            "gate": "unavailable",
            "tradingview": "not_observed",
            "timestamp": rendered_at,
        },
        "rendered_at": rendered_at,
    }


class DashboardHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        # Quiet logs; stderr stays clean for demo use.
        pass

    def _send_json(
        self, status: int, payload: dict[str, Any], *, cache_control: str | None = None
    ) -> None:
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        if cache_control:
            self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, relative: str) -> None:
        path = (FRONTEND_DIST / relative).resolve()
        if not path.is_relative_to(FRONTEND_DIST.resolve()) or not path.is_file():
            self.send_error(404, "not found")
            return
        content_type, _ = mimetypes.guess_type(str(path))
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "sapphire-alpha-dashboard-local",
                    "version": "0.2.0-local",
                    "timestamp": _utc_now(),
                },
            )
            return

        if self.path == "/api/build":
            self._send_json(200, _runtime_build_identity(), cache_control="no-store")
            return

        if self.path == "/api/v1/readiness":
            self._send_json(200, _runtime_readiness(), cache_control="no-store")
            return

        if self.path == "/api/v1/live":
            try:
                self._send_json(200, _build_live_snapshot())
            except Exception as exc:  # pragma: no cover - defensive
                self._send_json(503, {"detail": f"snapshot unavailable: {exc}"})
            return

        if self.path == "/api/v1/moss":
            self._send_json(200, _empty_moss_snapshot())
            return

        if self.path == "/api/fleet":
            self._send_json(200, _empty_fleet_counts())
            return

        if self.path == "/api/v1/widgets":
            self._send_json(200, _empty_widgets())
            return

        # Static asset routes.
        if self.path.startswith("/assets/"):
            self._serve_static(self.path.lstrip("/"))
            return

        if self.path in {"/sapphire-icon.svg", "/rag-map.html"}:
            self._serve_static(self.path.lstrip("/"))
            return

        # SPA catch-all.
        self._serve_static("index.html")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local Sapphire Alpha dashboard fallback"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="port to listen on"
    )
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind")
    args = parser.parse_args()

    if not FRONTEND_DIST.is_dir():
        print(
            f"frontend/dist not found at {FRONTEND_DIST}; run 'npm run build' first",
            file=sys.stderr,
        )
        return 1

    server = HTTPServer((args.host, args.port), DashboardHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Sapphire Alpha local dashboard at {url}")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

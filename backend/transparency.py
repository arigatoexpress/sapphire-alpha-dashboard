"""Transparency pane — projections over the trade-rail explanation ledger.

The Telegram rail's FREE-REIGN mode (telegram-bot/explain.py) appends one
structured record per auto-decision to ``explanations.jsonl``: signal source
and features, strategy track, deskos walk-forward verification stats, a
plain-English thesis, the risk bounds applied, and (as later lines, never
rewrites) post-trade outcome attribution.

This module is read-only over that ledger and serves two projections,
mirroring the live-telemetry operator/public split:

* operator — full detail (auth required outside PUBLIC_READ_ONLY).
* public   — whitelist projection: hashed ids, coarse USD bands instead of
  dollar amounts, no chat/wallet/token fields ever pass through.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("dashboard.transparency")

LEDGER_NAME = "explanations.jsonl"
MAX_RECORDS = 200

_BANDS = ((5, "<$5"), (10, "$5–10"), (25, "$10–25"), (50, "$25–50"),
          (100, "$50–100"), (float("inf"), ">$100"))

# Operator projection is still a whitelist — defense in depth against a
# hostile/extended ledger line carrying chat ids or secrets.
_OPERATOR_KEYS = ("schema", "kind", "id", "ts", "mode", "lane", "signal",
                  "strategy", "verification", "thesis", "action", "instrument",
                  "size_usd", "risk_bounds", "outcome")


def usd_band(usd: Any) -> str:
    try:
        usd = float(usd)
    except (TypeError, ValueError):
        return "unknown"
    if usd < 0:
        return "unknown"
    for hi, label in _BANDS:
        if usd < hi or hi == float("inf"):
            return label
    return "unknown"


def read_ledger(path: Path, limit: int = MAX_RECORDS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and row.get("schema") == 1:
                    rows.append(row)
    except OSError:
        pass
    except Exception as exc:  # noqa: BLE001 — pane must never 500 the app
        log.warning("explanations ledger read failed: %s", exc)
    return rows[-limit:] if limit else rows


def operator_record(rec: dict[str, Any]) -> dict[str, Any]:
    return {k: rec.get(k) for k in _OPERATOR_KEYS}


def public_record(rec: dict[str, Any]) -> dict[str, Any]:
    v = rec.get("verification") or {}
    outcome = rec.get("outcome") or None
    pnl = (outcome or {}).get("pnl_usd", 0)
    return {
        "id": hashlib.sha256(str(rec.get("id")).encode()).hexdigest()[:10],
        "ts": rec.get("ts"),
        "kind": rec.get("kind"),
        "mode": rec.get("mode"),
        "action": rec.get("action"),
        "instrument": str(rec.get("instrument") or "").split(":")[0].upper(),
        "size_band": usd_band(rec.get("size_usd")),
        "lane": rec.get("lane"),
        "strategy_track": (rec.get("strategy") or {}).get("track"),
        "verified": bool(v.get("verified")),
        "thesis": str(rec.get("thesis") or "")[:280],
        "outcome_band": usd_band(abs(pnl)) if outcome else None,
        "outcome_sign": ("+" if pnl >= 0 else "-") if outcome else None,
        "public_view": True,
    }


def snapshot(path: Path, *, public: bool,
             limit: int = MAX_RECORDS) -> dict[str, Any]:
    rows = read_ledger(path, limit=limit)
    project = public_record if public else operator_record
    records = [project(r) for r in rows]
    n_auto = sum(1 for r in rows if r.get("kind") == "auto_execution")
    n_verified = sum(1 for r in rows
                     if (r.get("verification") or {}).get("verified"))
    lanes: dict[str, int] = {}
    for r in rows:
        lane = r.get("lane")
        if lane:
            lanes[lane] = lanes.get(lane, 0) + 1
    out: dict[str, Any] = {
        "records": records,
        "counts": {"total": len(rows), "auto_executions": n_auto,
                   "verified": n_verified, "lanes": lanes,
                   "outcomes": sum(1 for r in rows if r.get("kind") == "outcome")},
        "source": LEDGER_NAME,
    }
    if public:
        out["public_view"] = True
        out["public_policy"] = ("Sizes and outcomes are shown as coarse bands; "
                                "identifiers are hashed.")
    return out

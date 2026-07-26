"""
Telegram Mini App surface — auth + read-only projections.

The Mini App is a *viewing* surface only. All approvals/arming continue to flow
through the existing Telegram bot rail (inline ✅/❌ buttons + /bots ARM). This
module deliberately exposes no mutating endpoints; the frontend deep-links back
to the bot chat for any decision.

Auth model (server-side, never trust the client):
  * The page sends the raw Telegram `initData` string in the header
    ``Authorization: tma <initData>``.
  * We validate it per https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app :
      secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token)
      hash       = hex(HMAC_SHA256(key=secret_key, msg=data_check_string))
    where data_check_string is all fields except ``hash``, sorted, joined with \n.
  * ``auth_date`` must be fresh (default 24h) and the Telegram user id must be
    in the ``TG_MINIAPP_ALLOWED_IDS`` allowlist.
  * The whole surface is INERT unless a bot token is configured
    (``TELEGRAM_BOT_TOKEN`` env or ``TELEGRAM_BOT_TOKEN_FILE``).

No secrets live in this file; the bot token is read from the environment at
request time so tests and deploys can control it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl

# --- chains ---------------------------------------------------------------
# Multi-chain-ready: every projected entity carries a `chain` tag.
KNOWN_CHAINS: dict[int, str] = {
    4663: "rh-chain",
    4326: "megaeth",
}
DEFAULT_CHAIN_ID = 4663


def tag_chain(entity: dict[str, Any], chain_id: int | None = None) -> dict[str, Any]:
    """Return a copy of *entity* tagged with chain_id/chain name."""
    cid = chain_id if chain_id is not None else int(entity.get("chain_id", DEFAULT_CHAIN_ID))
    out = dict(entity)
    out["chain_id"] = cid
    out["chain"] = KNOWN_CHAINS.get(cid, f"chain-{cid}")
    return out


# --- initData validation --------------------------------------------------


class InitDataError(Exception):
    """Raised when Telegram initData fails validation."""


@dataclass(frozen=True)
class TelegramUser:
    id: int
    username: str
    first_name: str


def _bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if token:
        return token
    path = os.environ.get("TELEGRAM_BOT_TOKEN_FILE", "").strip()
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    return ""


def _allowed_ids() -> set[int]:
    raw = os.environ.get("TG_MINIAPP_ALLOWED_IDS", "")
    out: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.add(int(part))
    return out


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_s: int = 86400,
    now: float | None = None,
) -> TelegramUser:
    """Validate a raw Telegram WebApp initData string; return the user.

    Raises InitDataError on any failure. Does NOT check the allowlist —
    callers decide authorization separately from authentication.
    """
    if not bot_token:
        raise InitDataError("bot token not configured")
    if not init_data or len(init_data) > 8192:
        raise InitDataError("missing or oversized initData")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        raise InitDataError("missing hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("bad signature")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as exc:
        raise InitDataError("bad auth_date") from exc
    current = time.time() if now is None else now
    if auth_date <= 0 or current - auth_date > max_age_s:
        raise InitDataError("initData expired")

    try:
        user_raw = json.loads(pairs.get("user", "{}"))
        user_id = int(user_raw["id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise InitDataError("missing user") from exc

    return TelegramUser(
        id=user_id,
        username=str(user_raw.get("username", "")),
        first_name=str(user_raw.get("first_name", "")),
    )


def authenticate_header(authorization: str | None) -> TelegramUser:
    """Full auth for API routes: parse `tma` header, validate, enforce allowlist."""
    if not authorization or not authorization.lower().startswith("tma "):
        raise InitDataError("missing tma authorization")
    user = validate_init_data(authorization[4:].strip(), _bot_token())
    allowed = _allowed_ids()
    if not allowed or user.id not in allowed:
        raise InitDataError("user not allowed")
    return user


# --- projections ----------------------------------------------------------


def _text(
    raw: dict[str, Any],
    keys: tuple[str, ...],
    *,
    fallback: str | None = None,
    limit: int = 240,
) -> str | None:
    """Return one bounded scalar as display text without forwarding its field name."""
    for key in keys:
        value = raw.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            text = " ".join(str(value).split()).strip()
            if text:
                return text[:limit]
    return fallback


def _chain_id(raw: dict[str, Any]) -> int | None:
    value = raw.get("chain_id")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def sanitize_proposal(raw: dict[str, Any], idx: int) -> dict[str, Any]:
    """Whitelist the context needed to triage a pending decision.

    Raw identifiers, people/source fields, chat metadata, and secrets never
    enter the result. The synthetic id is deliberately unrelated to producer
    ids, which may themselves encode a private source.
    """
    if not isinstance(raw, dict):
        raw = {}

    urgency = (_text(raw, ("urgency", "priority"), limit=24) or "").lower()
    urgency = {
        "urgent": "critical",
        "medium": "normal",
    }.get(urgency, urgency)
    if urgency not in {"critical", "high", "normal", "low"}:
        urgency = "unspecified"

    out = {
        "id": f"proposal-{idx:03d}",
        "action": _text(raw, ("action", "type"), fallback="Decision", limit=48),
        "instrument": _text(raw, ("instrument", "symbol"), fallback="—", limit=48),
        "side": _text(raw, ("side",), fallback="—", limit=24),
        "urgency": urgency,
        "expires_at": _text(raw, ("expires_at", "expiry", "deadline"), limit=64),
        "impact": _text(
            raw,
            ("impact", "impact_summary", "expected_impact"),
            limit=240,
        ),
        "created_at": _text(raw, ("created_at", "timestamp", "ts"), limit=64),
    }
    return tag_chain(out, _chain_id(raw))


def sanitize_decision(raw: dict[str, Any], idx: int) -> dict[str, Any]:
    """Display-safe, chain-tagged view of one decisions.jsonl row.

    Only decision semantics cross the boundary. Producer ids and any fields
    identifying a person or information source are omitted by construction.
    """
    if not isinstance(raw, dict):
        return tag_chain({"id": f"dec-{idx:03d}", "summary": "unreadable entry"})

    outcome = _text(raw, ("outcome", "result", "reason", "note"), fallback="", limit=240)
    out = {
        "id": f"dec-{idx:03d}",
        "action": _text(raw, ("action", "type"), fallback="Decision", limit=48),
        "instrument": _text(raw, ("instrument", "symbol"), fallback="—", limit=48),
        "side": _text(raw, ("side",), fallback="—", limit=24),
        "decision": _text(raw, ("decision", "status"), fallback="unknown", limit=32),
        "outcome": outcome,
        "reason": outcome,
        "timestamp": _text(raw, ("timestamp", "ts", "created_at"), limit=64),
    }
    return tag_chain(out, _chain_id(raw))

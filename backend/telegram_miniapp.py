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


def sanitize_decision(raw: dict[str, Any], idx: int) -> dict[str, Any]:
    """Display-safe, chain-tagged view of one decisions.jsonl row.

    Strips PII/secret-shaped keys; keeps decision semantics for history review.
    """
    if not isinstance(raw, dict):
        return tag_chain({"id": f"dec-{idx:03d}", "summary": "unreadable entry"})
    blocked = {"chat_id", "user_id", "username", "first_name", "last_name", "phone", "email"}
    safe: dict[str, Any] = {}
    for key, value in raw.items():
        low = str(key).lower()
        if low in blocked or "secret" in low or "password" in low or "token" in low:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[low] = value
    out = {
        "id": safe.get("id", f"dec-{idx:03d}"),
        "action": safe.get("action", safe.get("type", "decision")),
        "instrument": safe.get("instrument", safe.get("symbol", "—")),
        "side": safe.get("side", "—"),
        "decision": safe.get("decision", safe.get("status", "—")),
        "reason": safe.get("reason", safe.get("note", "")),
        "timestamp": safe.get("timestamp", safe.get("ts", safe.get("created_at", ""))),
    }
    cid = safe.get("chain_id")
    return tag_chain(out, int(cid) if isinstance(cid, (int, float)) else None)

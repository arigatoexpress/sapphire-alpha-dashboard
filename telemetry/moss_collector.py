"""Forward the local masked MOSS observer snapshot to its dedicated cloud lane.

This process is the trust boundary: browser code never receives the HMAC secret,
and the general system telemetry schema remains wallet-blind.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.request
from pathlib import Path
from typing import Any


_MASKED_RE = re.compile(r"^0x[a-fA-F0-9]{4}…[a-fA-F0-9]{4}$")
_UNITS_RE = re.compile(r"^\d+(?:\.\d+)?$")
_BLOCK_RE = re.compile(r"^\d+$")
_EXPECTED = {"version", "chainId", "identityHint", "eth", "usdm", "blockNumber", "observedAt"}


def _units(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 80 or not _UNITS_RE.fullmatch(value):
        raise ValueError("observer units are invalid")
    return value


def build_payload(state: Any, *, sequence: int | None = None) -> dict[str, Any]:
    if not isinstance(state, dict) or set(state) != _EXPECTED:
        raise ValueError("observer state has unsupported or missing fields")
    if state["version"] != 1:
        raise ValueError("observer version is unsupported")
    if state["chainId"] != 4326:
        raise ValueError("observer chain mismatch")
    if not isinstance(state["identityHint"], str) or not _MASKED_RE.fullmatch(state["identityHint"]):
        raise ValueError("observer identity must remain masked")
    if not isinstance(state["blockNumber"], str) or not _BLOCK_RE.fullmatch(state["blockNumber"]):
        raise ValueError("observer block is invalid")
    if not isinstance(state["observedAt"], str) or len(state["observedAt"]) > 48:
        raise ValueError("observer timestamp is invalid")
    return {
        "version": 1,
        "observed_at": state["observedAt"],
        "sequence": time.time_ns() if sequence is None else sequence,
        "chain": "MegaETH Mainnet",
        "identity_masked": state["identityHint"],
        "usdm": _units(state["usdm"]),
        "eth": _units(state["eth"]),
        "block": state["blockNumber"],
    }


def signed_headers(
    body: bytes,
    secret: str,
    *,
    timestamp: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    if len(secret) < 32:
        raise ValueError("MOSS_TELEMETRY_INGEST_SECRET must be at least 32 characters")
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


def read_state(path: Path) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"MOSS observer state unavailable at {path}") from exc
    return state if isinstance(state, dict) else {}


def push(payload: dict[str, Any], *, endpoint: str, secret: str, timeout: float = 10.0) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers=signed_headers(body, secret),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read())
    return result if isinstance(result, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Project the masked local MOSS observation")
    parser.add_argument("--push", action="store_true", help="submit to SAPPHIRE_MOSS_TELEMETRY_ENDPOINT")
    parser.add_argument("--state", type=Path, default=Path.home() / "ops-state" / "moss-wallet" / "observer.json")
    args = parser.parse_args()
    payload = build_payload(read_state(args.state))
    if args.push:
        endpoint = os.getenv("SAPPHIRE_MOSS_TELEMETRY_ENDPOINT", "").strip()
        secret = os.getenv("MOSS_TELEMETRY_INGEST_SECRET", "")
        if not endpoint:
            raise SystemExit("SAPPHIRE_MOSS_TELEMETRY_ENDPOINT is required with --push")
        print(json.dumps(push(payload, endpoint=endpoint, secret=secret), sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

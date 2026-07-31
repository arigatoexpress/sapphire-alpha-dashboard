"""Forward a sanitized `fleet-lease export` snapshot to the durable cloud lane."""

from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.request
from pathlib import Path
from typing import Any


_EXPECTED = {"generated_at", "leases", "gates", "counts"}


def build_payload(
    state: Any,
    *,
    sequence: int | None = None,
) -> dict[str, Any]:
    if not isinstance(state, dict) or set(state) != _EXPECTED:
        raise ValueError("fleet snapshot has unsupported or missing fields")
    leases = state["leases"]
    gates = state["gates"]
    counts = state["counts"]
    if (
        not isinstance(state["generated_at"], str)
        or not isinstance(leases, list)
        or not isinstance(gates, list)
        or not isinstance(counts, dict)
        or counts != {"leases": len(leases), "gates_open": len(gates)}
    ):
        raise ValueError("fleet snapshot counts are invalid")
    return {
        "version": 1,
        "generated_at": state["generated_at"],
        "sequence": time.time_ns() if sequence is None else sequence,
        "leases": copy.deepcopy(leases),
        "gates": copy.deepcopy(gates),
        "counts": copy.deepcopy(counts),
    }


def signed_headers(
    body: bytes,
    secret: str,
    *,
    timestamp: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    if len(secret) < 32:
        raise ValueError(
            "TELEMETRY_INGEST_SECRET must be at least 32 characters"
        )
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
        raise ValueError(f"sanitized fleet snapshot unavailable at {path}") from exc
    return state if isinstance(state, dict) else {}


def push(
    payload: dict[str, Any],
    *,
    endpoint: str,
    secret: str,
    timeout: float = 10.0,
) -> dict[str, Any]:
    body = json.dumps(
        payload,
        separators=(",", ":"),
        allow_nan=False,
        sort_keys=True,
    ).encode()
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
    parser = argparse.ArgumentParser(
        description="Project one sanitized fleet coordination snapshot"
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="submit to SAPPHIRE_FLEET_TELEMETRY_ENDPOINT",
    )
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    payload = build_payload(read_state(args.state))
    if args.push:
        endpoint = os.getenv("SAPPHIRE_FLEET_TELEMETRY_ENDPOINT", "").strip()
        secret = os.getenv("TELEMETRY_INGEST_SECRET", "")
        if not endpoint:
            raise SystemExit(
                "SAPPHIRE_FLEET_TELEMETRY_ENDPOINT is required with --push"
            )
        print(
            json.dumps(
                push(payload, endpoint=endpoint, secret=secret),
                sort_keys=True,
            )
        )
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed verification for production dependency and asset inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LOCKS = (ROOT / "frontend/package-lock.json", ROOT / "web/package-lock.json")
ASSETS = ROOT / "deploy/assets.sha256.json"
FONT_NAMES = {
    "@fontsource/inter",
    "@fontsource/jetbrains-mono",
    "@fontsource/newsreader",
    "@fontsource/space-grotesk",
}
HEX64 = re.compile(r"[0-9a-f]{64}")


class InputViolation(ValueError):
    """An immutable input contract did not match."""


def verify_lock(path: Path) -> dict[str, int]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("lockfileVersion") != 3 or lock.get("requires") is not True:
        raise InputViolation("package lock contract mismatch")
    packages = lock.get("packages")
    root = packages.get("") if isinstance(packages, dict) else None
    if not isinstance(root, dict):
        raise InputViolation("package manifest is missing")

    remote = 0
    for name, package in packages.items():
        if not name or not isinstance(package, dict):
            continue
        resolved = package.get("resolved")
        if resolved is None:
            continue
        if not isinstance(resolved, str) or not resolved.startswith(
            "https://registry.npmjs.org/"
        ):
            raise InputViolation("non-registry package source")
        integrity = package.get("integrity")
        if not isinstance(integrity, str) or not integrity.startswith("sha512-"):
            raise InputViolation("package integrity missing")
        remote += 1
    if remote == 0:
        raise InputViolation("empty dependency closure")
    return {"packages": len(packages) - 1, "remote_packages": remote}


def _download_sha256(url: str) -> str:
    request = Request(url, headers={"User-Agent": "sapphire-input-verifier/1"})
    context = ssl.create_default_context()
    digest = hashlib.sha256()
    with urlopen(request, timeout=30, context=context) as response:  # noqa: S310
        if response.status != 200:
            raise InputViolation("asset fetch failed")
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_assets(*, network: bool) -> dict[str, int]:
    manifest = json.loads(ASSETS.read_text(encoding="utf-8"))
    if manifest.get("schema") != "sapphire/network-assets/v1":
        raise InputViolation("asset schema mismatch")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or len(assets) != len(FONT_NAMES):
        raise InputViolation("asset cardinality mismatch")
    seen: set[str] = set()
    lock_urls: dict[str, set[str]] = {name: set() for name in FONT_NAMES}
    for lock_path in LOCKS:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        for name in FONT_NAMES:
            package = lock["packages"].get(f"node_modules/{name}")
            if not isinstance(package, dict):
                raise InputViolation("font dependency missing from package lock")
            url = package.get("resolved")
            integrity = package.get("integrity")
            if not isinstance(url, str) or not isinstance(integrity, str):
                raise InputViolation("font lock identity missing")
            lock_urls[name].add(url)

    for asset in assets:
        if not isinstance(asset, dict):
            raise InputViolation("asset record mismatch")
        name_version = asset.get("name")
        url = asset.get("url")
        expected = asset.get("sha256")
        if not all(isinstance(value, str) for value in (name_version, url, expected)):
            raise InputViolation("asset identity missing")
        name, separator, version = name_version.rpartition("@")
        if separator != "@" or name not in FONT_NAMES or version != "5.3.0":
            raise InputViolation("unexpected asset")
        if name in seen or lock_urls[name] != {url}:
            raise InputViolation("asset URL does not match dependency locks")
        if HEX64.fullmatch(expected) is None:
            raise InputViolation("asset SHA-256 is invalid")
        if network and _download_sha256(url) != expected:
            raise InputViolation("asset SHA-256 mismatch")
        seen.add(name)
    if seen != FONT_NAMES:
        raise InputViolation("asset set mismatch")
    return {"assets": len(seen), "network_verified": len(seen) if network else 0}


def verify(*, network_assets: bool = False) -> dict[str, Any]:
    return {
        "schema": "sapphire/build-input-verification/v1",
        "ok": True,
        "locks": {
            path.relative_to(ROOT).as_posix(): verify_lock(path) for path in LOCKS
        },
        "assets": verify_assets(network=network_assets),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network-assets", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(network_assets=args.network_assets)
    except Exception:
        result = {
            "schema": "sapphire/build-input-verification/v1",
            "ok": False,
            "error": "input contract mismatch",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

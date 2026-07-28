#!/usr/bin/env python3
"""Start the one supported, loopback-only owner approval runtime."""

from __future__ import annotations

import importlib.metadata
import os
from pathlib import Path
import stat
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PYTHON = (PROJECT_ROOT / "backend" / ".venv" / "bin" / "python").resolve()
OWNER = "ari"
HOST = "127.0.0.1"
PORT = "8099"
REQUIRED_DISTRIBUTIONS = {
    "fastapi": "0.115.7",
    "pydantic": "2.8.2",
    "starlette": "0.45.3",
    "uvicorn": "0.30.6",
}


def _private_key(path: Path) -> bool:
    try:
        metadata = path.lstat()
        return (
            path.resolve(strict=True) == path
            and not path.is_symlink()
            and stat.S_ISREG(metadata.st_mode)
            and metadata.st_nlink == 1
            and stat.S_IMODE(metadata.st_mode) == 0o600
            and (not hasattr(os, "geteuid") or metadata.st_uid == os.geteuid())
        )
    except OSError:
        return False


def main() -> None:
    if Path(sys.executable).resolve() != EXPECTED_PYTHON:
        raise SystemExit("OWNER_RUNTIME_PYTHON_MISMATCH")
    if os.environ.get("AUTH_USERNAME") != OWNER:
        raise SystemExit("OWNER_RUNTIME_IDENTITY_MISMATCH")
    if len(os.environ.get("AUTH_PASSWORD", "")) < 12:
        raise SystemExit("OWNER_RUNTIME_PASSWORD_MISSING")
    if any(os.environ.get(marker) for marker in ("K_SERVICE", "CONTAINER")):
        raise SystemExit("OWNER_RUNTIME_CLOUD_REFUSED")
    for distribution, expected in REQUIRED_DISTRIBUTIONS.items():
        if importlib.metadata.version(distribution) != expected:
            raise SystemExit("OWNER_RUNTIME_DEPENDENCY_MISMATCH")
    certificate = Path(os.environ.get("OWNER_APPROVAL_TLS_CERT", "")).resolve()
    private_key = Path(os.environ.get("OWNER_APPROVAL_TLS_KEY", "")).resolve()
    if not certificate.is_file() or not _private_key(private_key):
        raise SystemExit("OWNER_RUNTIME_TLS_MISSING")
    session_parent = Path.home() / "Library" / "Application Support" / "Sapphire"
    session_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    session_parent.chmod(0o700)
    arguments = [
        str(EXPECTED_PYTHON),
        "-I",
        "-m",
        "uvicorn",
        "backend.local_owner_main:app",
        "--app-dir",
        str(PROJECT_ROOT),
        "--host",
        HOST,
        "--port",
        PORT,
        "--ssl-certfile",
        str(certificate),
        "--ssl-keyfile",
        str(private_key),
        "--no-server-header",
    ]
    os.execve(str(EXPECTED_PYTHON), arguments, dict(os.environ))


if __name__ == "__main__":
    main()

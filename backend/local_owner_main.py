"""Loopback-only Sapphire owner approval application.

This module is excluded from the Cloud Run entrypoint. The checked local
launcher is the only supported way to start it.
"""

from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import FastAPI

try:
    from . import owner_approval
except ImportError:
    import owner_approval


OWNER = owner_approval.OWNER_IDENTITY
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def authenticate_owner(username: str, password: str) -> str:
    configured_owner = os.environ.get("AUTH_USERNAME", "")
    configured_password = os.environ.get("AUTH_PASSWORD", "")
    if (
        configured_owner != OWNER
        or len(configured_password) < 12
        or not hmac.compare_digest(username, configured_owner)
        or not hmac.compare_digest(password, configured_password)
    ):
        raise owner_approval.RailRefused("AUTH_INVALID", 401)
    return OWNER


app = FastAPI(
    title="Sapphire local owner approval rail",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(
    owner_approval.create_owner_approval_router(
        owner_approval.production_rail(),
        authenticate=authenticate_owner,
        asset_dir=_FRONTEND_DIST,
        containerized=lambda: False,
    )
)

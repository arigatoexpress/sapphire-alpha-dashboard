"""Fresh telemetry must never be reused from an intermediary or browser cache."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ["AUTH_USERNAME"] = "testuser"
os.environ["AUTH_PASSWORD"] = "testpass-strong-99"

from main import app


client = TestClient(app)


def test_live_telemetry_response_forbids_caching():
    response = client.get("/api/v1/live")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"

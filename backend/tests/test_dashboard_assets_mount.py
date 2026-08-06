"""Mission Control SPA asset mount — /dashboard/assets must not return HTML."""

from __future__ import annotations

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)
AUTH = ("testuser", "testpass-strong-99")


def test_dashboard_assets_served_as_js(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text(
        "<!doctype html><script type='module' src='/dashboard/assets/app.js'></script>"
        "<div id='root'></div>"
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("export const ok = 1;")
    monkeypatch.setattr(main, "_FRONTEND_DIST_DIR", tmp_path)

    r = client.get("/dashboard/assets/app.js")
    assert r.status_code == 200
    assert "export const ok" in r.text
    assert "text/html" not in r.headers.get("content-type", "")

    shell = client.get("/dashboard")
    assert shell.status_code == 200
    assert "root" in shell.text

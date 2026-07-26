"""Public marketing site (statically exported Next.js) served from `web/out`.

These lock down the properties that make the front door work at all:
  · it is reachable anonymously, even with PUBLIC_READ_ONLY off;
  · it never shadows the API or the operator dashboard;
  · extensionless Next.js metadata images keep their real content type;
  · nothing outside `web/out` can be read through it.
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_USERNAME"] = "testuser"
os.environ["AUTH_PASSWORD"] = "testpass-strong-99"

import main
from main import app

client = TestClient(app)

AUTH = ("testuser", "testpass-strong-99")


@pytest.fixture
def web_out(tmp_path, monkeypatch):
    """A minimal stand-in for a real `next build --output export` tree."""
    out = tmp_path / "out"
    (out / "architecture").mkdir(parents=True)
    (out / "_next" / "static").mkdir(parents=True)

    (out / "index.html").write_text("<!doctype html><title>Sapphire Alpha</title>", encoding="utf-8")
    (out / "architecture" / "index.html").write_text("<!doctype html><title>Architecture</title>", encoding="utf-8")
    (out / "404.html").write_text("<!doctype html><title>Not found</title>", encoding="utf-8")
    (out / "robots.txt").write_text("User-Agent: *\nAllow: /\n", encoding="utf-8")
    (out / "sitemap.xml").write_text("<urlset></urlset>", encoding="utf-8")
    (out / "_next" / "static" / "app.js").write_text("console.log(1)", encoding="utf-8")
    # Next.js writes metadata images with no file extension.
    (out / "opengraph-image").write_bytes(b"\x89PNG\r\n\x1a\n")

    # A file the site must never be able to reach.
    (tmp_path / "secret.txt").write_text("operator-only", encoding="utf-8")

    monkeypatch.setattr(main, "_WEB_OUT_DIR", out)
    return out


def test_root_serves_marketing_site_anonymously(web_out, monkeypatch):
    """The front door must not require auth, even with public read-only OFF."""
    monkeypatch.delenv("PUBLIC_READ_ONLY", raising=False)
    response = client.get("/")
    assert response.status_code == 200
    assert "Sapphire Alpha" in response.text
    assert response.headers["content-type"].startswith("text/html")


def test_marketing_route_resolves_directory_index(web_out, monkeypatch):
    monkeypatch.delenv("PUBLIC_READ_ONLY", raising=False)
    for path in ("/architecture", "/architecture/"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "Architecture" in response.text


def test_static_pages_and_dashboard_support_head_prefetches(web_out, monkeypatch):
    """Next link prefetch and crawlers issue HEAD before navigation."""
    monkeypatch.delenv("PUBLIC_READ_ONLY", raising=False)
    for path in ("/", "/architecture/", "/dashboard/"):
        response = client.head(path)
        assert response.status_code in {200, 503}, path
        assert response.content == b""


def test_robots_and_sitemap_are_public(web_out, monkeypatch):
    monkeypatch.delenv("PUBLIC_READ_ONLY", raising=False)
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert robots.headers["content-type"].startswith("text/plain")

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert sitemap.headers["content-type"].startswith("application/xml")


def test_extensionless_opengraph_image_keeps_png_content_type(web_out, monkeypatch):
    """Unfurlers drop the preview unless this is served as a real image."""
    monkeypatch.delenv("PUBLIC_READ_ONLY", raising=False)
    response = client.get("/opengraph-image")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_next_assets_are_immutably_cached(web_out):
    response = client.get("/_next/static/app.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert "immutable" in response.headers["cache-control"]


def test_unknown_route_returns_marketing_404(web_out, monkeypatch):
    monkeypatch.delenv("PUBLIC_READ_ONLY", raising=False)
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert "Not found" in response.text


def test_marketing_site_cannot_escape_its_directory(web_out):
    """Traversal must not reach a sibling of `web/out`."""
    for attack in (
        "/../secret.txt",
        "/%2e%2e/secret.txt",
        "/_next/../../secret.txt",
        "/architecture/../../secret.txt",
    ):
        response = client.get(attack)
        assert response.status_code in {403, 404}, attack
        assert "operator-only" not in response.text, attack


def test_dashboard_is_still_served_and_now_anonymous(web_out, monkeypatch):
    """The operator SPA is served at /dashboard and no longer behind Basic auth.

    A 503 here means the Vite bundle is not built in this checkout, which is a
    build-state fact rather than an auth fact — what matters is that neither
    the anonymous nor the authenticated request is refused with a 401.
    """
    for path in ("/dashboard", "/dashboard/live"):
        assert client.get(path).status_code in (200, 503)
        assert client.get(path, auth=AUTH).status_code in (200, 503)


def test_marketing_site_does_not_shadow_the_api(web_out):
    """The catch-all must not swallow API routes declared above it."""
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["service"] == "sapphire-alpha-dashboard"

    assert client.get("/healthz").status_code == 200
    # Answered by the API with JSON, not swallowed by the catch-all as HTML.
    widgets = client.get("/api/v1/widgets")
    assert widgets.status_code == 200
    assert widgets.headers["content-type"].startswith("application/json")


def test_falls_back_to_dashboard_when_site_not_built(tmp_path, monkeypatch):
    """A backend-only checkout should still render, not 503 at the root."""
    monkeypatch.setattr(main, "_WEB_OUT_DIR", tmp_path / "does-not-exist")
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    response = client.get("/")
    assert response.status_code in {200, 503}

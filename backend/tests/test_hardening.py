"""Complementary hardening coverage.

Fills gaps left by test_smoke / test_public_mode / test_widgets:
  - AUTH_PASSWORD_SECRET file loading (happy path, precedence, whitespace,
    missing file, policy still enforced on file contents)
  - DASHBOARD_FORCE_KILLSWITCH / DASHBOARD_ARMED gate overrides
  - full security-header set, including on 401/404/403 error responses
  - raw path-traversal middleware ('..' path segments -> 403)
  - /api/health and /healthz response shape
  - auth gate details (wrong username, WWW-Authenticate challenge)
  - CORS env-driven behavior (subprocess: middleware is wired at import time)
  - /api/v1/tradingview/alerts not_configured fallback
  - SPA catch-all 503 when the frontend bundle is missing
  - deterministic slowapi rate-limit trip on /healthz (in-memory storage,
    reset before/after so no cross-test pollution)
  - _safe_bool / _safe_float coercion helpers
"""

import json
import os
import subprocess
import sys
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_USERNAME"] = "testuser"
os.environ["AUTH_PASSWORD"] = "testpass-strong-99"

import main
from main import app

client = TestClient(app)

AUTH = ("testuser", "testpass-strong-99")
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# AUTH_PASSWORD_SECRET file loading
# ---------------------------------------------------------------------------


def _subprocess_credentials(env: dict) -> subprocess.CompletedProcess:
    """Import main with a controlled env in a subprocess and resolve credentials.

    A subprocess keeps the lru_cache on _auth_credentials in this process
    untouched (every other test file relies on the cached test credentials).
    """
    code = (
        "import main;"
        "main._auth_credentials.cache_clear();"
        "print(repr(main._auth_credentials()))"
    )
    run_env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": BACKEND_DIR,
        **env,
    }
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        env=run_env,
    )


def test_password_secret_file_loaded(tmp_path):
    secret = tmp_path / "auth-password"
    secret.write_text("from-secret-file-99\n", encoding="utf-8")
    result = _subprocess_credentials(
        {"AUTH_USERNAME": "u", "AUTH_PASSWORD_SECRET": str(secret)}
    )
    assert result.returncode == 0, result.stderr
    # Whitespace/newline is stripped from the file contents.
    assert "('u', 'from-secret-file-99')" in result.stdout


def test_password_secret_file_takes_precedence_over_env(tmp_path):
    secret = tmp_path / "auth-password"
    secret.write_text("file-wins-password-1", encoding="utf-8")
    result = _subprocess_credentials(
        {
            "AUTH_USERNAME": "u",
            "AUTH_PASSWORD": "env-loses-password-1",
            "AUTH_PASSWORD_SECRET": str(secret),
        }
    )
    assert result.returncode == 0, result.stderr
    assert "file-wins-password-1" in result.stdout
    assert "env-loses" not in result.stdout


def test_password_secret_missing_file_fails_loud(tmp_path):
    result = _subprocess_credentials(
        {"AUTH_USERNAME": "u", "AUTH_PASSWORD_SECRET": str(tmp_path / "nope")}
    )
    assert result.returncode != 0
    assert "Failed to read AUTH_PASSWORD_SECRET" in result.stderr


def test_password_secret_file_still_subject_to_policy(tmp_path):
    secret = tmp_path / "auth-password"
    secret.write_text("short", encoding="utf-8")
    result = _subprocess_credentials(
        {"AUTH_USERNAME": "u", "AUTH_PASSWORD_SECRET": str(secret)}
    )
    assert result.returncode != 0
    assert "at least 12 characters" in result.stderr


def test_password_secret_empty_file_rejected(tmp_path):
    secret = tmp_path / "auth-password"
    secret.write_text("   \n", encoding="utf-8")
    result = _subprocess_credentials(
        {"AUTH_USERNAME": "u", "AUTH_PASSWORD_SECRET": str(secret)}
    )
    assert result.returncode != 0
    assert "must be set" in result.stderr


# ---------------------------------------------------------------------------
# Killswitch / armed gate overrides
# ---------------------------------------------------------------------------


@pytest.fixture
def gate_env(monkeypatch):
    """Pin every gate input via env so local state files cannot leak in."""
    monkeypatch.setenv("DASHBOARD_ARMED", "0")
    monkeypatch.setenv("DASHBOARD_FORCE_KILLSWITCH", "0")
    monkeypatch.setenv("DASHBOARD_MODE", "telegram")
    return monkeypatch


def test_force_killswitch_engages(gate_env):
    gate_env.setenv("DASHBOARD_FORCE_KILLSWITCH", "1")
    gate = main._gate_status()
    assert gate["state"] == "killswitch"
    assert gate["killswitch"] is True
    assert gate["label"] == "Killswitch engaged"


def test_killswitch_overrides_armed(gate_env):
    gate_env.setenv("DASHBOARD_ARMED", "1")
    gate_env.setenv("DASHBOARD_FORCE_KILLSWITCH", "1")
    gate = main._gate_status()
    assert gate["state"] == "killswitch"
    assert gate["armed"] is True  # armed flag preserved, state still killswitch


def test_armed_without_killswitch(gate_env):
    gate_env.setenv("DASHBOARD_ARMED", "1")
    gate = main._gate_status()
    assert gate["state"] == "armed"
    assert gate["killswitch"] is False


def test_disarmed_default(gate_env):
    gate = main._gate_status()
    assert gate["state"] == "disarmed"
    assert gate["armed"] is False
    assert gate["killswitch"] is False


def test_killswitch_visible_in_public_view(gate_env):
    """Anonymous viewers must still see the killswitch state (safety signal)."""
    gate_env.setenv("PUBLIC_READ_ONLY", "1")
    gate_env.setenv("DASHBOARD_FORCE_KILLSWITCH", "1")
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    data = r.json()
    assert data["public_view"] is True
    assert data["gate"]["state"] == "killswitch"
    assert data["gate"]["killswitch"] is True
    # But operator-only gate fields stay dropped.
    assert "cap_usd" not in data["gate"]
    assert "wallet_address" not in data["gate"]


def test_full_wallet_address_never_in_public_payload(gate_env):
    gate_env.setenv("PUBLIC_READ_ONLY", "1")
    full_addr = "0x1234567890abcdef1234567890abcdef12345678"
    gate_env.setenv("WALLET_ADDRESS", full_addr)
    for path in ("/api/v1/status", "/api/v1/widgets"):
        r = client.get(path)
        assert r.status_code == 200
        payload = r.json()
        body = json.dumps(payload)
        assert full_addr not in body, f"full wallet address leaked in {path}"
        assert "0x1234...5678" not in body
        assert payload["wallet"] == {"disclosure": "withheld"}


# ---------------------------------------------------------------------------
# Security headers — full set, on success AND error responses
# ---------------------------------------------------------------------------

EXPECTED_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


def _assert_security_headers(response):
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers.get(name) == value, f"missing/wrong {name}"


def test_security_headers_full_set_on_success():
    _assert_security_headers(client.get("/api/health"))


def test_security_headers_on_401(monkeypatch):
    # GETs are anonymous now, so /vault/rag-map — which keeps require_auth
    # unconditionally — is where a 401 can still be observed.
    r = client.get("/vault/rag-map")
    assert r.status_code == 401
    _assert_security_headers(r)


def test_security_headers_on_404():
    r = client.get("/assets/does-not-exist.js", auth=AUTH)
    assert r.status_code == 404
    _assert_security_headers(r)


def test_security_headers_on_traversal_403():
    r = client.get("/assets/%2e%2e/%2e%2e/etc/passwd", auth=AUTH)
    assert r.status_code == 403
    _assert_security_headers(r)


# ---------------------------------------------------------------------------
# Path traversal — raw-path middleware and assets guard variants
# ---------------------------------------------------------------------------


def test_traversal_middleware_rejects_dotdot_segments():
    # %2e%2e decodes to a literal '..' path segment before routing.
    r = client.get("/%2e%2e/%2e%2e/etc/passwd", auth=AUTH)
    assert r.status_code == 403
    assert r.json() == {"detail": "forbidden"}


def test_traversal_middleware_rejects_dotdot_after_valid_prefix():
    r = client.get("/api/v1/%2e%2e/%2e%2e/etc/passwd", auth=AUTH)
    assert r.status_code == 403


def test_assets_encoded_slash_traversal_blocked():
    # '..%2f..%2f' stays one path parameter; the resolve() guard must catch it.
    r = client.get("/assets/..%2f..%2fmain.py", auth=AUTH)
    assert r.status_code == 403


def test_assets_serves_only_real_files_within_dir(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('ok')")
    monkeypatch.setattr(main, "_FRONTEND_DIST_DIR", tmp_path)
    assert client.get("/assets/app.js", auth=AUTH).status_code == 200
    assert client.get("/assets/..%2fapp.js", auth=AUTH).status_code == 403


# ---------------------------------------------------------------------------
# Health endpoints — response shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/healthz", "/api/health"])
def test_health_shape(path):
    r = client.get(path)
    assert r.status_code == 200
    data = r.json()
    assert set(data) == {"status", "service", "version", "timestamp"}
    assert data["status"] == "ok"
    assert data["service"] == "sapphire-alpha-dashboard"
    # Timestamp must be valid ISO-8601 (dashboards sort on it).
    datetime.fromisoformat(data["timestamp"])


# ---------------------------------------------------------------------------
# Auth gate details
# ---------------------------------------------------------------------------


def test_wrong_username_rejected():
    r = client.get("/api/v1/widgets", auth=("not-the-user", "testpass-strong-99"))
    assert r.status_code == 401


def test_wrong_username_rejected_even_in_public_mode(monkeypatch):
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    r = client.get("/api/v1/status", auth=("not-the-user", "testpass-strong-99"))
    assert r.status_code == 401


def test_401_sends_basic_challenge():
    r = client.get("/vault/rag-map")
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate") == "Basic"


def test_non_get_still_challenges_anonymously():
    """Un-redacting reads must not un-protect writes."""
    r = client.post("/api/v1/status")
    assert r.status_code in (401, 405)
    if r.status_code == 401:
        assert r.headers.get("WWW-Authenticate") == "Basic"


def test_dashboard_is_anonymous_and_serves_only_the_static_bundle(monkeypatch, tmp_path):
    """The operator SPA is public now — it is a bundle, not a data source.

    Everything it renders comes from the API routes, which do their own
    sanitizing. Serving the bundle anonymously therefore discloses nothing that
    `GET /api/v1/live` does not already disclose on purpose.
    """
    (tmp_path / "index.html").write_text("<html>x</html>")
    monkeypatch.setattr(main, "_FRONTEND_DIST_DIR", tmp_path)
    assert client.get("/dashboard").status_code == 200
    assert client.get("/dashboard/any/spa/route").status_code == 200
    assert client.get("/dashboard", auth=AUTH).status_code == 200


def test_dashboard_503_when_bundle_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_FRONTEND_DIST_DIR", tmp_path / "empty")
    r = client.get("/dashboard", auth=AUTH)
    assert r.status_code == 503


def test_marketing_catchall_never_serves_operator_state(monkeypatch, tmp_path):
    """Opening `/` anonymously must not expose the operator bundle or API data."""
    monkeypatch.delenv("PUBLIC_READ_ONLY", raising=False)
    (tmp_path / "index.html").write_text("<html>OPERATOR-BUNDLE</html>")
    monkeypatch.setattr(main, "_FRONTEND_DIST_DIR", tmp_path)

    web_out = tmp_path / "out"
    web_out.mkdir()
    (web_out / "index.html").write_text("<html>marketing</html>")
    monkeypatch.setattr(main, "_WEB_OUT_DIR", web_out)

    r = client.get("/")
    assert r.status_code == 200
    assert "OPERATOR-BUNDLE" not in r.text
    # The root serves the marketing bundle and nothing else — the operator
    # bundle lives at /dashboard, which is a separate route, not a fallback.
    assert "OPERATOR-BUNDLE" in client.get("/dashboard").text
    # And the anonymous widgets payload is still the sanitized one.
    assert client.get("/api/v1/widgets").json().get("public_view") is True


# ---------------------------------------------------------------------------
# CORS (middleware is wired at import time -> subprocess for the enabled case)
# ---------------------------------------------------------------------------


def test_cors_disabled_by_default():
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_cors_allows_only_configured_origin():
    code = (
        "from fastapi.testclient import TestClient;"
        "import main;"
        "c = TestClient(main.app);"
        "ok = c.get('/api/health', headers={'Origin': 'https://dash.example'});"
        "bad = c.get('/api/health', headers={'Origin': 'https://evil.example'});"
        "print(ok.headers.get('access-control-allow-origin'));"
        "print(bad.headers.get('access-control-allow-origin'))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": BACKEND_DIR,
            "AUTH_USERNAME": "u",
            "AUTH_PASSWORD": "testpass-strong-99",
            "CORS_ORIGIN": "https://dash.example",
        },
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "https://dash.example"
    assert lines[1] == "None"


# ---------------------------------------------------------------------------
# TradingView alerts — authed fallback when no receiver is configured
# ---------------------------------------------------------------------------


def test_alerts_not_configured_fallback(monkeypatch):
    monkeypatch.delenv("TV_WEBHOOK_URL", raising=False)
    r = client.get("/api/v1/tradingview/alerts", auth=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data == {"alerts": [], "total": 0, "source": "not_configured"}


# ---------------------------------------------------------------------------
# Rate limiting — deterministic trip using in-memory storage
# ---------------------------------------------------------------------------


def test_healthz_rate_limit_trips_and_is_json():
    """/healthz is limited to 30/minute; the 31st request within the window
    must be a 429. In-memory slowapi storage is deterministic; reset before
    and after so other tests keep a clean budget."""
    main.limiter.reset()
    try:
        statuses = [client.get("/healthz").status_code for _ in range(31)]
        assert statuses[:30] == [200] * 30
        assert statuses[30] == 429
    finally:
        main.limiter.reset()


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def test_safe_bool():
    assert main._safe_bool(True) is True
    assert main._safe_bool("1") is True
    assert main._safe_bool("TRUE") is True
    assert main._safe_bool("yes") is True
    assert main._safe_bool("on") is True
    assert main._safe_bool("0") is False
    assert main._safe_bool("false") is False
    assert main._safe_bool("") is False
    assert main._safe_bool(None) is False


def test_safe_float():
    assert main._safe_float("1.5") == 1.5
    assert main._safe_float(None) == 0.0
    assert main._safe_float("nope") == 0.0
    assert main._safe_float("nope", default=7.0) == 7.0

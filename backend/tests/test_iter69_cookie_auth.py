"""Iteration 69 — Cookie Auth Migration regression tests.

Verifies:
  - Cookie-only login (no body access_token, HttpOnly auth+refresh cookies, readable CSRF cookie)
  - GET /api/auth/me via cookie jar
  - CSRF double-submit enforcement on mutating endpoints
  - Refresh cookie rotation
  - Logout deletes cookies
  - Bearer regression path via x-return-token: true
  - localStorage token absence is checked in frontend E2E, not here.
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

LEARNER = {"email": "uat-learner@ifpi.org", "password": "UatLearner!2026"}
ADMIN = {"email": "uat-admin@ifpi.org", "password": "UatAdmin!2026"}

AUTH_COOKIE = "ifpi_auth_token"
REFRESH_COOKIE = "ifpi_refresh_token"
CSRF_COOKIE = "ifpi_csrf"


# ---------- helpers ----------
# NOTE: /app/backend/tests/conftest.py auto-injects `X-Return-Token: true` on
# every request to preserve legacy Bearer tests. For cookie-only validation
# we mark the session with `_skip_x_return_token=True` and, for module-level
# `requests.post` calls, we explicitly pass `X-Return-Token: false` header
# (the shared patch only injects when the header is missing via setdefault).

def _cookie_session():
    s = requests.Session()
    s._skip_x_return_token = True  # opt out of legacy X-Return-Token injection
    return s


def _login_cookie(creds=LEARNER):
    s = _cookie_session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    return s, r


def _login_bearer(creds=LEARNER):
    # module-level requests.post auto-injects X-Return-Token: true via conftest
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json=creds,
        headers={"x-return-token": "true"},
        timeout=20,
    )
    return r


# ---------- cookie-mode ----------
class TestCookieLogin:
    def test_login_returns_no_body_token_and_sets_cookies(self):
        s, r = _login_cookie()
        assert r.status_code == 200, r.text
        body = r.json()
        # body must not contain access_token
        assert body.get("access_token") in (None, ""), f"access_token leaked in body: {body.get('access_token')!r}"
        # user object present
        assert "user" in body and body["user"].get("email") == LEARNER["email"]
        # cookies present
        set_cookie_headers = r.headers.get("set-cookie", "") or ""
        # requests coalesces multi Set-Cookie via .raw; use session jar too
        jar = {c.name: c for c in s.cookies}
        assert AUTH_COOKIE in jar, f"missing {AUTH_COOKIE} cookie: {list(jar)}"
        assert REFRESH_COOKIE in jar, f"missing {REFRESH_COOKIE} cookie: {list(jar)}"
        assert CSRF_COOKIE in jar, f"missing {CSRF_COOKIE} cookie: {list(jar)}"
        # HttpOnly enforcement — inspect raw header for HttpOnly on auth cookies
        raw = set_cookie_headers.lower()
        # ifpi_auth_token must have HttpOnly
        m = re.search(rf"{AUTH_COOKIE}=[^;]+;[^,]*httponly", raw)
        assert m, f"{AUTH_COOKIE} missing HttpOnly flag. Raw: {set_cookie_headers[:500]}"
        m = re.search(rf"{REFRESH_COOKIE}=[^;]+;[^,]*httponly", raw)
        assert m, f"{REFRESH_COOKIE} missing HttpOnly flag."
        # CSRF cookie must be readable (no HttpOnly)
        # Extract the CSRF cookie segment
        csrf_seg_match = re.search(rf"{CSRF_COOKIE}=[^,]+", set_cookie_headers, re.IGNORECASE)
        assert csrf_seg_match, "csrf cookie segment missing"
        assert "httponly" not in csrf_seg_match.group(0).lower(), "CSRF cookie must NOT be HttpOnly"

    def test_me_with_cookie_jar(self):
        s, _ = _login_cookie()
        r = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("email") == LEARNER["email"]


class TestCSRF:
    def _find_mutating_endpoint(self, s):
        # /api/auth/logout is a mutating endpoint protected by CSRF
        return f"{BASE_URL}/api/auth/logout"

    def test_mutation_without_csrf_header_returns_403(self):
        s, _ = _login_cookie()
        s._skip_csrf_autoinject = True  # conftest otherwise auto-mirrors CSRF from cookie
        url = self._find_mutating_endpoint(s)
        r = s.post(url, timeout=15)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"
        # body should reference CSRF
        assert "csrf" in r.text.lower(), f"expected CSRF error, got: {r.text[:200]}"

    def test_mutation_with_csrf_header_succeeds(self):
        s, _ = _login_cookie()
        csrf = s.cookies.get(CSRF_COOKIE)
        assert csrf, "CSRF cookie missing"
        # test with a non-logout mutation first to check enforcement broadly
        # Try posting a comment or enrolment isn't guaranteed here; use logout as final step
        r = s.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"X-CSRF-Token": csrf},
            timeout=15,
        )
        assert r.status_code == 200, f"logout w/ CSRF failed: {r.status_code} {r.text[:200]}"


class TestRefresh:
    def test_refresh_rotates_cookies(self):
        s, _ = _login_cookie()
        old_auth = s.cookies.get(AUTH_COOKIE)
        old_refresh = s.cookies.get(REFRESH_COOKIE)
        assert old_auth and old_refresh
        r = s.post(f"{BASE_URL}/api/auth/refresh", timeout=15)
        assert r.status_code == 200, r.text
        new_auth = s.cookies.get(AUTH_COOKIE)
        new_refresh = s.cookies.get(REFRESH_COOKIE)
        assert new_auth, "auth cookie not reset after refresh"
        # rotation: at least one of the two should be different (typically both)
        assert (new_auth != old_auth) or (new_refresh != old_refresh), "refresh did not rotate cookies"


class TestLogoutDeletesCookies:
    def test_logout_sets_max_age_zero(self):
        s, _ = _login_cookie()
        csrf = s.cookies.get(CSRF_COOKIE)
        r = s.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"X-CSRF-Token": csrf},
            timeout=15,
        )
        assert r.status_code == 200
        raw = (r.headers.get("set-cookie") or "").lower()
        for name in (AUTH_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
            assert name.lower() in raw, f"{name} not in logout Set-Cookie header"
        # Max-Age=0 expected for deletion
        assert "max-age=0" in raw, f"expected Max-Age=0 deletion, raw={raw[:500]}"
        # /me must now 401
        me = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert me.status_code == 401, f"expected 401 after logout, got {me.status_code}"


class TestBearerRegression:
    def test_x_return_token_returns_body_token(self):
        r = _login_bearer()
        assert r.status_code == 200, r.text
        body = r.json()
        token = body.get("access_token")
        assert token and isinstance(token, str) and len(token) > 20, f"missing access_token in body: {body}"

    def test_bearer_hits_me(self):
        r = _login_bearer()
        token = r.json()["access_token"]
        me = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert me.status_code == 200, me.text
        assert me.json()["email"] == LEARNER["email"]

    def test_bearer_mutation_without_csrf_succeeds(self):
        r = _login_bearer()
        token = r.json()["access_token"]
        # logout is a mutation; Bearer must be CSRF-exempt
        out = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert out.status_code == 200, f"Bearer logout failed: {out.status_code} {out.text[:200]}"


class TestBreadthRegression:
    """A few protected GETs across routers to ensure cookie auth propagates."""

    @pytest.fixture(scope="class")
    def session(self):
        s, r = _login_cookie()
        assert r.status_code == 200
        return s

    @pytest.mark.parametrize("path", [
        "/api/courses",
        "/api/learning-paths",
        "/api/leaderboard",
        "/api/auth/me",
    ])
    def test_protected_get(self, session, path):
        r = session.get(f"{BASE_URL}{path}", timeout=20)
        # Some endpoints may 404 if not present; only fail on 401/403 auth errors
        assert r.status_code not in (401, 403), f"{path} auth failed: {r.status_code} {r.text[:200]}"

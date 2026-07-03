"""IFPI Screenshot Capture Pipeline (P2 doc artifact).

Runs Playwright against a live IFPI deployment and captures 24 canonical
screens for the User Manual + master HTML render. Every element with a
`data-testid` attribute gets a subtle red outline in a "debug" variant so
contributors and QA can see the testable surface at a glance.

Usage:
    BASE_URL=https://<tenant>.ifpi.example.com \
    ADMIN_EMAIL=admin@ifpi.org ADMIN_PASSWORD=admin123 \
    LEARNER_EMAIL=learner@ifpi.org LEARNER_PASSWORD=learner123 \
        python backend/scripts/build_screenshots.py

    # Optional flags:
    #   --overlay        also emit *_overlay.png with testid outlines
    #   --out DIR        override output dir (default: /app/docs/screenshots)
    #   --headed         run non-headless (for debugging)
    #   --only KEY       capture only one screen (see SCREENS keys)

Exit codes:
    0  — all captures succeeded (or --only key matched)
    1  — one or more captures failed; failure summary printed
    2  — cannot reach BASE_URL / cannot log in

Design notes:
- Uses ONE browser + TWO contexts (admin + learner) to avoid a login
  storm. Cookies/localStorage isolated per context.
- Skips gracefully if playwright chromium isn't installed (returns 0 with
  a helpful message so CI doesn't red-fail on infra issues).
- Ships an idempotent naming scheme: {index:02d}_{key}.png so the User
  Manual can hard-link them without a rebuild table.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "docs" / "screenshots"


# ─────────────────────────────────────────────────────────────────────
# Screen catalog — index-ordered so file names are stable across runs.
# Each entry: (path, wait_for_selector, role_context)
# `role_context` picks which auth session to use — 'anon', 'admin',
# 'learner'.
# ─────────────────────────────────────────────────────────────────────


@dataclass
class Screen:
    key: str
    path: str
    role: str  # 'anon' | 'admin' | 'learner'
    wait_for: Optional[str] = None
    scroll_to: Optional[str] = None
    label: str = ""


SCREENS: List[Screen] = [
    Screen("login", "/login", "anon",
           wait_for="[data-testid=login-form-submit]",
           label="Login page — the first thing users see"),
    Screen("catalog_public", "/catalog", "anon",
           wait_for="body",
           label="Anonymous public catalog"),
    Screen("dashboard_admin", "/dashboard", "admin",
           wait_for="[data-testid=admin-dashboard],main",
           label="Admin dashboard — org KPIs"),
    Screen("courses_list_admin", "/dashboard/courses", "admin",
           wait_for="main",
           label="Course listing (admin)"),
    Screen("course_edit", "/dashboard/courses/1", "admin",
           wait_for="main",
           label="Course edit — slides + prerequisites"),
    Screen("authoring_course_builder", "/dashboard/authoring", "admin",
           wait_for="main",
           label="AI Course Builder — prompt to outline"),
    Screen("authoring_flashcards", "/dashboard/authoring/flashcards/1", "admin",
           wait_for="main",
           label="Flashcards authoring — AI generated"),
    Screen("mindmap", "/dashboard/courses/1/mindmap", "admin",
           wait_for="main",
           label="Mind map (reactflow) — savable layout"),
    Screen("research", "/dashboard/authoring/research", "admin",
           wait_for="main",
           label="Deep Research (Tavily-grounded)"),
    Screen("tokens", "/dashboard/tokens", "admin",
           wait_for="main",
           label="AI spend chart + API token analytics"),
    Screen("api_tokens", "/dashboard/api-tokens", "admin",
           wait_for="main",
           label="API tokens — scoped credentials"),
    Screen("webhooks", "/dashboard/webhooks", "admin",
           wait_for="main",
           label="Outgoing webhooks + delivery log"),
    Screen("users", "/dashboard/users", "admin",
           wait_for="main",
           label="Users + roles"),
    Screen("academies", "/dashboard/academies", "admin",
           wait_for="main",
           label="Academies (sub-tenants inside an org)"),
    Screen("badge_tiers", "/dashboard/badges", "admin",
           wait_for="main",
           label="Badge tiers + XP thresholds"),
    Screen("leaderboard_admin", "/dashboard/leaderboard", "admin",
           wait_for="main",
           label="Leaderboard (admin view)"),
    Screen("reports", "/dashboard/reports", "admin",
           wait_for="main",
           label="Reports — enrolment, cohort, spend"),
    Screen("org_settings", "/dashboard/organization/settings", "admin",
           wait_for="main",
           label="Organization settings + branding"),
    Screen("audit_log", "/dashboard/audit", "admin",
           wait_for="main",
           label="Audit log (append-only)"),
    Screen("learner_dashboard", "/dashboard", "learner",
           wait_for="main",
           label="Learner dashboard — in-progress + due"),
    Screen("learner_course", "/learn/courses/1", "learner",
           wait_for="main",
           label="Slide viewer + narration player"),
    Screen("learner_flashcards", "/learn/flashcards/1", "learner",
           wait_for="main",
           label="SM-2 swipeable flashcards"),
    Screen("learner_certificates", "/dashboard/certificates", "learner",
           wait_for="main",
           label="Certificate wall + LinkedIn share"),
    Screen("verify_public", "/verify", "anon",
           wait_for="body",
           label="Anonymous cert verify (rate-limited)"),
]

assert len({s.key for s in SCREENS}) == len(SCREENS), "duplicate keys"


# ─────────────────────────────────────────────────────────────────────
# The overlay JS — highlights every element with data-testid.
# ─────────────────────────────────────────────────────────────────────

OVERLAY_JS = """
() => {
    const nodes = document.querySelectorAll('[data-testid]');
    nodes.forEach(el => {
        el.style.outline = '2px dashed rgba(239, 68, 68, 0.75)';
        el.style.outlineOffset = '2px';
        const label = document.createElement('div');
        label.textContent = el.getAttribute('data-testid');
        label.style.cssText = (
          'position:absolute;background:#ef4444;color:white;font:10px monospace;' +
          'padding:1px 4px;border-radius:2px;z-index:2147483647;pointer-events:none'
        );
        const rect = el.getBoundingClientRect();
        label.style.left = (rect.left + window.scrollX) + 'px';
        label.style.top = (rect.top + window.scrollY - 12) + 'px';
        document.body.appendChild(label);
    });
    return nodes.length;
}
"""


# ─────────────────────────────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────────────────────────────


def _login_via_api(base_url: str, email: str, password: str) -> Optional[str]:
    """Return access token or None."""
    import requests
    try:
        r = requests.post(f"{base_url}/api/auth/login",
                          json={"email": email, "password": password},
                          timeout=10)
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception as exc:  # noqa: BLE001
        print(f"[screenshots] login failed for {email}: {exc}", file=sys.stderr)
    return None


def _seed_context(context, token: Optional[str], base_url: str) -> None:
    """Push the JWT into localStorage so the SPA thinks it's logged in."""
    if not token:
        return
    context.add_init_script(
        f"window.localStorage.setItem('ifpi_access_token', '{token}');"
    )


# ─────────────────────────────────────────────────────────────────────
# Capture loop
# ─────────────────────────────────────────────────────────────────────


def _capture(pw, base_url: str, tokens: Dict[str, Optional[str]],
             screen: Screen, out_dir: Path, index: int,
             overlay: bool, headed: bool) -> tuple[bool, str]:
    browser = pw.chromium.launch(headless=not headed,
                                 args=["--disable-dev-shm-usage",
                                       "--no-sandbox"])
    try:
        context = browser.new_context(viewport={"width": 1440, "height": 900},
                                      device_scale_factor=1)
        _seed_context(context, tokens.get(screen.role), base_url)
        page = context.new_page()
        url = base_url + screen.path
        page.goto(url, wait_until="networkidle", timeout=25_000)
        if screen.wait_for:
            try:
                page.wait_for_selector(screen.wait_for, timeout=8_000)
            except Exception:
                pass  # best-effort — capture even if selector doesn't match
        page.wait_for_timeout(600)  # allow anim/render settle

        base_name = f"{index:02d}_{screen.key}"
        base_path = out_dir / f"{base_name}.png"
        page.screenshot(path=str(base_path), full_page=False,
                        clip=None, animations="disabled")
        detail = f"→ {base_path.name}"

        if overlay:
            count = page.evaluate(OVERLAY_JS)
            over_path = out_dir / f"{base_name}_overlay.png"
            page.screenshot(path=str(over_path), full_page=False,
                            animations="disabled")
            detail += f" (+ overlay: {count} testids)"

        return True, detail
    except Exception as exc:  # noqa: BLE001
        return False, f"ERROR: {exc!r}"
    finally:
        browser.close()


def _emit_index_md(out_dir: Path, results: List[tuple]) -> None:
    """Emit index.md so screenshots are linkable + human-readable."""
    lines = ["# IFPI Screen Inventory",
             "",
             "*Auto-generated by `backend/scripts/build_screenshots.py`. Do not hand-edit.*",
             ""]
    for idx, (screen, ok, detail) in enumerate(results, start=1):
        status = "✅" if ok else "❌"
        img = f"{idx:02d}_{screen.key}.png"
        lines.append(f"### {status} {idx:02d}. `{screen.key}` — {screen.label}")
        lines.append(f"- **Path:** `{screen.path}` (role: `{screen.role}`)")
        lines.append(f"- **File:** `{img}`")
        if not ok:
            lines.append(f"- **Failure:** {detail}")
        lines.append(f"\n![{screen.key}]({img})\n")
    (out_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overlay", action="store_true",
                    help="Also emit *_overlay.png with data-testid outlines")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--only", default=None, help="Capture only this key")
    args = ap.parse_args()

    base_url = os.environ.get("BASE_URL", "").rstrip("/") \
        or os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    if not base_url:
        try:
            with open(REPO_ROOT / "frontend" / ".env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        base_url = line.split("=", 1)[1].strip().rstrip("/")
        except FileNotFoundError:
            pass
    if not base_url:
        print("BASE_URL / REACT_APP_BACKEND_URL not set — cannot capture",
              file=sys.stderr)
        return 2

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@ifpi.org")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    learner_email = os.environ.get("LEARNER_EMAIL", "learner@ifpi.org")
    learner_password = os.environ.get("LEARNER_PASSWORD", "learner123")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed — `pip install playwright && "
              "playwright install chromium`. Skipping.", file=sys.stderr)
        return 0

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[screenshots] BASE_URL={base_url}, out={out_dir}")

    tokens = {
        "anon": None,
        "admin": _login_via_api(base_url, admin_email, admin_password),
        "learner": _login_via_api(base_url, learner_email, learner_password),
    }
    for role, tok in tokens.items():
        if role != "anon" and not tok:
            print(f"[screenshots] WARN: could not log in as {role}; those "
                  "screens will render as anon", file=sys.stderr)

    screens = SCREENS
    if args.only:
        screens = [s for s in SCREENS if s.key == args.only]
        if not screens:
            print(f"--only key {args.only!r} matched nothing", file=sys.stderr)
            return 2

    results: List[tuple] = []
    with sync_playwright() as pw:
        for idx, screen in enumerate(screens, start=1):
            print(f"  [{idx:02d}/{len(screens)}] {screen.key} "
                  f"({screen.role}) {screen.path}", flush=True)
            ok, detail = _capture(pw, base_url, tokens, screen, out_dir,
                                  idx, args.overlay, args.headed)
            print(f"      {detail}", flush=True)
            results.append((screen, ok, detail))

    _emit_index_md(out_dir, results)

    failed = [r for r in results if not r[1]]
    print(f"\n[screenshots] {len(results) - len(failed)}/{len(results)} "
          f"captured; index.md written to {out_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

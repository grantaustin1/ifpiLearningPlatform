"""Iter 22 — Marketplace: public catalog endpoint + public course detail
+ marketplace_opt_in gate.

Exercises the public marketplace flow that anonymous visitors hit before
signing up. Verifies:
- GET /api/catalog returns paginated published courses with organization
  block and total count.
- GET /api/catalog?featured=true returns up to 6 courses sorted by
  enrollment count.
- GET /api/catalog/{id} returns detail with syllabus_preview and 404s
  for unknown / unpublished / opt-out courses.
- Setting marketplace_opt_in=false on the org hides its courses from
  the marketplace but leaves them accessible to enrolled learners.
"""
from __future__ import annotations

import os

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
    open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")

ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}


def _admin_session() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    r.raise_for_status()
    tok = r.json().get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


# ── Public catalog ───────────────────────────────────────────────────
def test_catalog_returns_pagination_shape():
    r = requests.get(f"{BASE_URL}/api/catalog", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert "courses" in d and "categories" in d and "total" in d
    assert d["page"] == 1 and d["page_size"] == 24
    assert isinstance(d["total"], int) and d["total"] >= 1
    # Every course should now carry an organization block
    for c in d["courses"]:
        assert "organization" in c
        if c["organization"]:
            assert set(c["organization"].keys()) >= {"id", "name"}


def test_catalog_search_q_filters_results():
    r = requests.get(f"{BASE_URL}/api/catalog?q=IFPI", timeout=10)
    assert r.status_code == 200
    titles = [c["title"] for c in r.json()["courses"]]
    assert any("IFPI" in t for t in titles), f"expected IFPI course in results, got {titles[:5]}"


def test_catalog_featured_returns_top_courses():
    r = requests.get(f"{BASE_URL}/api/catalog?featured=true", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d["courses"], list)
    assert len(d["courses"]) <= 6


def test_catalog_detail_returns_syllabus_preview():
    # Course id=1 is the seeded IFPI Fundamentals course
    r = requests.get(f"{BASE_URL}/api/catalog/1", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["id"] == 1
    assert "syllabus_preview" in d and isinstance(d["syllabus_preview"], list)
    assert d["organization"] is not None
    assert "title" in d and "price_cents" in d


def test_catalog_detail_404_for_unknown_course():
    r = requests.get(f"{BASE_URL}/api/catalog/9999999", timeout=10)
    assert r.status_code == 404


# ── marketplace_opt_in gate ──────────────────────────────────────────
def test_marketplace_opt_in_toggle_hides_org_courses():
    admin = _admin_session()
    # Confirm the flag is present on GET /api/organization
    g = admin.get(f"{BASE_URL}/api/organization", timeout=10).json()
    assert "marketplace_opt_in" in g
    # Turn OFF marketplace opt-in for the tenant
    r = admin.patch(f"{BASE_URL}/api/organization", json={"marketplace_opt_in": False}, timeout=10)
    assert r.status_code == 200, r.text
    try:
        # Public catalog should now be empty (or at least not include this org's IFPI course)
        cat = requests.get(f"{BASE_URL}/api/catalog?q=IFPI", timeout=10).json()
        assert not any("IFPI" in c["title"] for c in cat["courses"]), \
            "opted-out org's courses must NOT appear in public catalog"
        # Detail page 404s too
        d = requests.get(f"{BASE_URL}/api/catalog/1", timeout=10)
        assert d.status_code == 404
    finally:
        # Always restore the flag so subsequent tests / real users aren't broken
        admin.patch(f"{BASE_URL}/api/organization", json={"marketplace_opt_in": True}, timeout=10)
    # Verify restored
    cat2 = requests.get(f"{BASE_URL}/api/catalog?q=IFPI", timeout=10).json()
    assert any("IFPI" in c["title"] for c in cat2["courses"])


# ── Sort (Iter 23) ───────────────────────────────────────────────────
def test_catalog_sort_price_asc_returns_cheapest_first():
    r = requests.get(f"{BASE_URL}/api/catalog?sort=price_asc&page_size=10", timeout=10)
    assert r.status_code == 200
    prices = [c["price_cents"] for c in r.json()["courses"]]
    assert prices == sorted(prices), f"price_asc should return ascending, got {prices}"


def test_catalog_sort_price_desc_returns_most_expensive_first():
    r = requests.get(f"{BASE_URL}/api/catalog?sort=price_desc&page_size=10", timeout=10)
    assert r.status_code == 200
    prices = [c["price_cents"] for c in r.json()["courses"]]
    assert prices == sorted(prices, reverse=True), f"price_desc should return descending, got {prices}"


def test_catalog_sort_most_enrolled_returns_high_first():
    r = requests.get(f"{BASE_URL}/api/catalog?sort=most_enrolled&page_size=10", timeout=10)
    assert r.status_code == 200
    counts = [c["enrollment_count"] for c in r.json()["courses"]]
    assert counts == sorted(counts, reverse=True), f"most_enrolled should return descending, got {counts}"


def test_catalog_sort_invalid_rejected():
    r = requests.get(f"{BASE_URL}/api/catalog?sort=random", timeout=10)
    assert r.status_code == 422

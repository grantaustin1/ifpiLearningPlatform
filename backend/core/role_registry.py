"""Canonical role registry — mirrors ERP360's `core/role_registry.py` pattern.

LMS-specific roles only. When SSO maps from ERP360, the SSO bridge applies a
translation table (see `services/sso_service.py`).
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Iterable, List

CANONICAL_ROLE_REGISTRY: "OrderedDict[str, str]" = OrderedDict([
    ("SUPER_ADMIN", "Platform super-admin — can manage all academies"),
    ("ADMIN", "Academy administrator — full control of one academy"),
    ("INSTRUCTOR", "Can create courses/exams and grade learners"),
    ("BILLING_VIEWER", "Read-only access to billing/invoicing"),
    ("LEARNER", "End-user enrolled in courses (default)"),
])

CANONICAL_ROLE_NAMES = tuple(CANONICAL_ROLE_REGISTRY.keys())
CANONICAL_ROLE_SET = set(CANONICAL_ROLE_NAMES)

# Aliases tolerated from external systems / legacy data
ROLE_ALIAS_TO_CANONICAL = {
    "OWNER": "ADMIN",
    "MANAGER": "ADMIN",
    "PLATFORM_ADMIN": "SUPER_ADMIN",
    "TRAINER": "INSTRUCTOR",
    "STUDENT": "LEARNER",
    "USER": "LEARNER",
}

# Sets used for permission checks
ADMIN_ROLES = frozenset({"SUPER_ADMIN", "ADMIN"})
INSTRUCTOR_ROLES = frozenset({"SUPER_ADMIN", "ADMIN", "INSTRUCTOR"})
BILLING_ROLES = frozenset({"SUPER_ADMIN", "ADMIN", "BILLING_VIEWER"})


def normalize_role_name(role: str | None) -> str:
    if not role:
        return ""
    token = role.strip().upper().replace(" ", "_").replace("-", "_")
    return ROLE_ALIAS_TO_CANONICAL.get(token, token)


def normalize_role_names(roles: Iterable[str]) -> List[str]:
    out, seen = [], set()
    for r in roles or []:
        c = normalize_role_name(r)
        if c and c not in seen:
            out.append(c)
            seen.add(c)
    return out


def is_known_role(role: str) -> bool:
    return normalize_role_name(role) in CANONICAL_ROLE_SET

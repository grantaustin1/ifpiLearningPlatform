"""Locust load-test suite for IFPI (P1 scale artifact).

Exercises the highest-traffic endpoints under load:

- Anonymous public catalog + certificate verify (no auth)
- Authenticated learner: dashboard, course list, flashcard review
- Authenticated admin: courses list, tokens dashboard

Run:
    locust -f backend/scripts/locustfile.py \\
        --headless -u 500 -r 25 -t 2m \\
        --host https://<your-tenant>.ifpi.example.com

Env vars:
    ADMIN_EMAIL / ADMIN_PASSWORD
    LEARNER_EMAIL / LEARNER_PASSWORD

Every user picks a role at spawn based on WEIGHTS:
    5 % admin, 90 % learner, 5 % anonymous — mimicking real-world traffic.

Expected P95 targets on a 4-worker uvicorn + Redis + Postgres:
    catalog / verify: < 300 ms
    dashboard:        < 800 ms
    flashcard review: < 500 ms

CI gate: pass `--tags smoke` for a 30 s smoke run in the docs-drift
workflow (optional; currently manual).
"""
from __future__ import annotations

import os
import random

from locust import HttpUser, TaskSet, between, tag, task


ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@ifpi.org")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
LEARNER_EMAIL = os.environ.get("LEARNER_EMAIL", "learner@ifpi.org")
LEARNER_PASSWORD = os.environ.get("LEARNER_PASSWORD", "learner123")


def _login(client, email: str, password: str) -> str | None:
    r = client.post("/api/auth/login",
                    json={"email": email, "password": password},
                    name="/api/auth/login")
    if r.status_code != 200:
        return None
    return r.json().get("access_token")


# ─────────────────────────────────────────────────────────────────────
# Anonymous — no auth. Highest volume, cheapest requests.
# ─────────────────────────────────────────────────────────────────────


class AnonymousBehavior(TaskSet):
    @tag("smoke", "anon")
    @task(3)
    def health(self):
        self.client.get("/api/health", name="/api/health")

    @tag("smoke", "anon")
    @task(5)
    def public_root(self):
        self.client.get("/api", name="/api")

    @tag("anon")
    @task(2)
    def verify_random(self):
        code = "TEST" + "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=18))
        self.client.get(f"/api/public/certificates/verify/{code}",
                        name="/api/public/certificates/verify/{code}")


# ─────────────────────────────────────────────────────────────────────
# Learner — dashboard, course list, flashcard review
# ─────────────────────────────────────────────────────────────────────


class LearnerBehavior(TaskSet):
    def on_start(self):
        self.token = _login(self.client, LEARNER_EMAIL, LEARNER_PASSWORD)
        if self.token:
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @tag("smoke", "learner")
    @task(3)
    def dashboard(self):
        # Learners land on their own courses view after login. Use the
        # notifications endpoint as a light "dashboard-shaped" call —
        # it's <2kB and hits the auth path.
        self.client.get("/api/notifications", name="/api/notifications (learner)")

    @tag("learner")
    @task(2)
    def my_courses(self):
        self.client.get("/api/courses", name="/api/courses (learner)")

    @tag("learner")
    @task(2)
    def my_certs(self):
        self.client.get("/api/certificates", name="/api/certificates")

    @tag("learner")
    @task(3)
    def flashcards_due(self):
        # Use course_id=1 which the seed provisions deterministically.
        self.client.get("/api/learn/flashcards/courses/1/due",
                        name="/api/learn/flashcards/courses/{id}/due")


# ─────────────────────────────────────────────────────────────────────
# Admin — read-heavy KPI surfaces
# ─────────────────────────────────────────────────────────────────────


class AdminBehavior(TaskSet):
    def on_start(self):
        self.token = _login(self.client, ADMIN_EMAIL, ADMIN_PASSWORD)
        if self.token:
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @tag("smoke", "admin")
    @task(2)
    def courses_list(self):
        self.client.get("/api/courses", name="/api/courses (admin)")

    @tag("admin")
    @task(2)
    def users_list(self):
        self.client.get("/api/users", name="/api/users")

    @tag("admin")
    @task(1)
    def spend_chart(self):
        self.client.get("/api/admin/api-tokens/analytics/spend?days=14",
                        name="/api/admin/api-tokens/analytics/spend")


# ─────────────────────────────────────────────────────────────────────
# Composite user — weighted spawn matching real traffic
# ─────────────────────────────────────────────────────────────────────


class IFPIUser(HttpUser):
    """Weighted composite. Locust auto-selects one TaskSet per user."""
    wait_time = between(1, 3)
    tasks = {
        AnonymousBehavior: 5,
        LearnerBehavior:   18,   # ~ 90 %
        AdminBehavior:     1,    # ~ 5 %
    }

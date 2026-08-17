"""One-off: create AI-generated, auto-graded quiz gates for the 4 module
courses. Uses the live API so all validation/audit paths run."""
import os
import sys

import requests

API = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API = line.split("=", 1)[1].strip()
assert API

r = requests.post(f"{API}/api/auth/login", json={
    "email": "qa-admin@ifpi.org", "password": "QaAdmin!2026"})
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}"}

COURSES = {
    294: "Module 1: Anatomy & Physiology — Knowledge Check",
    295: "Module 2: Utilizing the Fitness Facility — Knowledge Check",
    296: "Module 3: Principles of Exercise Training — Knowledge Check",
    297: "Module 2: Group Exercise & Choreography — Knowledge Check",
}

existing = {e.get("course_id"): e for e in
            requests.get(f"{API}/api/exams", headers=H).json()}

for cid, title in COURSES.items():
    if cid in existing:
        print(f"exam already exists for course {cid} — skipped")
        continue
    exam = requests.post(f"{API}/api/exams", headers=H, json={
        "title": title, "course_id": cid, "passing_score": 70,
        "max_attempts": 3, "randomize": True, "is_published": False,
    }).json()
    eid = exam["id"]
    print(f"created exam {eid} for course {cid}")

    gen = requests.post(f"{API}/api/exams/ai-generate-questions", headers=H,
                        json={"course_id": cid, "num_questions": 10},
                        timeout=300)
    if gen.status_code != 200:
        print(f"  AI generation FAILED for {cid}: {gen.status_code} {gen.text[:200]}")
        continue
    qs = gen.json()["questions"]
    for i, q in enumerate(qs):
        q["order_index"] = i
    put = requests.put(f"{API}/api/exams/{eid}/questions", headers=H, json=qs)
    print(f"  questions saved: {put.status_code} count={len(qs)}")
    pub = requests.patch(f"{API}/api/exams/{eid}", headers=H,
                         json={"is_published": True})
    print(f"  published: {pub.status_code}")
print("done")

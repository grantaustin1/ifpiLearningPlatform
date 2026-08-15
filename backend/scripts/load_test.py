"""Concurrent learner load test — measures p50/p95/p99 latency + error rate.

Simulates N learners doing: login → list courses → open course detail →
enroll → save progress → serve a slide image. Run against localhost to
measure the backend without proxy noise.

Usage:
    python scripts/load_test.py --base http://localhost:8001 --users 30 --loops 5
    python scripts/load_test.py --label after_phase1
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx

LEARNER = {"email": "uat-learner@ifpi.org", "password": "UatLearner!2026"}
COURSE_ID = 243
IMG = "/api/uploads/files/imports/327/slides/slide-01.jpg"


async def learner_session(client: httpx.AsyncClient, base: str, loops: int,
                          results: dict, token: str):
    async def timed(name, method, url, **kw):
        t0 = time.perf_counter()
        try:
            r = await client.request(method, base + url, **kw)
            ok = r.status_code < 500
        except Exception:
            ok = False
            r = None
        results.setdefault(name, []).append(
            (time.perf_counter() - t0, ok))
        return r

    h = {"Authorization": f"Bearer {token}"}
    for i in range(loops):
        await timed("courses_list", "GET", "/api/courses", headers=h)
        await timed("course_detail", "GET", f"/api/courses/{COURSE_ID}", headers=h)
        await timed("enroll", "POST", f"/api/courses/{COURSE_ID}/enroll", headers=h)
        await timed("progress", "POST", f"/api/courses/{COURSE_ID}/progress",
                    headers=h, json={"slide_index": i % 20})
        await timed("slide_image", "GET", IMG)
        await timed("notifications", "GET", "/api/notifications", headers=h)
        await timed("leaderboard", "GET", "/api/gamification/leaderboard", headers=h)
        await timed("catalog", "GET", "/api/catalog")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8001")
    ap.add_argument("--users", type=int, default=30)
    ap.add_argument("--loops", type=int, default=5)
    ap.add_argument("--label", default="baseline")
    args = ap.parse_args()

    results: dict = {}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(args.base + "/api/auth/login", json=LEARNER)
        token = r.json().get("access_token") or r.json().get("token")
        t0 = time.perf_counter()
        await asyncio.gather(*[
            learner_session(client, args.base, args.loops, results, token)
            for _ in range(args.users)])
        wall = time.perf_counter() - t0

    summary = {"label": args.label, "users": args.users, "loops": args.loops,
               "wall_seconds": round(wall, 1), "endpoints": {}}
    total_reqs = total_errors = 0
    for name, samples in sorted(results.items()):
        lat = sorted(s[0] for s in samples)
        errs = sum(1 for s in samples if not s[1])
        total_reqs += len(samples)
        total_errors += errs
        summary["endpoints"][name] = {
            "n": len(samples), "errors": errs,
            "p50_ms": round(statistics.median(lat) * 1000, 1),
            "p95_ms": round(lat[int(len(lat) * 0.95) - 1] * 1000, 1),
            "p99_ms": round(lat[int(len(lat) * 0.99) - 1] * 1000, 1),
            "max_ms": round(lat[-1] * 1000, 1),
        }
    summary["total_requests"] = total_reqs
    summary["total_errors"] = total_errors
    summary["rps"] = round(total_reqs / wall, 1)

    out = Path("/app/memory/load_tests.json")
    history = json.loads(out.read_text()) if out.exists() else []
    history.append(summary)
    out.write_text(json.dumps(history, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    asyncio.run(main())

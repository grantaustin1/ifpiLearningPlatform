"""Download the curated cover-photo library into local storage (Iter 43).

Idempotent — skips files that already exist.
Run:  cd /app/backend && python scripts/build_cover_library.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE = Path(__file__).resolve().parents[1] / "uploads" / "covers"
LIB = BASE / "library"

PHOTOS = {
    "weights_rack.jpg": "https://images.unsplash.com/photo-1571902943202-507ec2618e8f?w=1200&q=80",
    "personal_training.jpg": "https://images.unsplash.com/photo-1541534741688-6078c6bfb5c5?w=1200&q=80",
    "yoga_class.jpg": "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=1200&q=80",
    "running_track.jpg": "https://images.unsplash.com/photo-1554284126-aa88f22d8b74?w=1200&q=80",
    "boxing_training.jpg": "https://images.unsplash.com/photo-1599058917212-d750089bc07e?w=1200&q=80",
    "kettlebell_workout.jpg": "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=1200&q=80",
    "nutrition_coaching.jpg": "https://images.unsplash.com/photo-1574680096145-d05b474e2155?w=1200&q=80",
    "outdoor_fitness.jpg": "https://images.unsplash.com/photo-1434682881908-b43d0467b798?w=1200&q=80",
    "spin_class.jpg": "https://images.unsplash.com/photo-1571388208497-71bedc66e932?w=1200&q=80",
    "stretching_mobility.jpg": "https://images.unsplash.com/photo-1532029837206-abbe2b7620e3?w=1200&q=80",
    "gym_studio.jpg": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=1200&q=80",
}

# Reuse the four photos already downloaded for the seeded courses.
EXISTING = {
    "gym_interior.jpg": BASE / "ifpi_fundamentals.jpg",
    "barbell_strength.jpg": BASE / "exercise_science.jpg",
    "client_consultation.jpg": BASE / "client_onboarding.jpg",
    "equipment_floor.jpg": BASE / "health_safety.jpg",
}


def main() -> None:
    LIB.mkdir(parents=True, exist_ok=True)
    for name, src in EXISTING.items():
        dest = LIB / name
        if not dest.exists() and src.exists():
            shutil.copyfile(src, dest)
            print(f"• copied {name}")
    for name, url in PHOTOS.items():
        dest = LIB / name
        if dest.exists():
            print(f"• {name} already present — skipped")
            continue
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        assert resp.headers.get("content-type", "").startswith("image/"), name
        dest.write_bytes(resp.content)
        print(f"• downloaded {name} ({len(resp.content) // 1024} KB)")
    print(f"done — {len(list(LIB.glob('*.jpg')))} photos in the library")


if __name__ == "__main__":
    main()

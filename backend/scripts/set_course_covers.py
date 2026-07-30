"""Set real cover photos on the seeded fitness courses.

Downloads curated fitness stock photos once into the local storage backend
(/app/backend/uploads/covers/…) and points each course's `cover_image` at the
public /api/uploads/files/... URL.

Run:  cd /app/backend && python scripts/set_course_covers.py
      DATABASE_URL=sqlite:////app/backend/snapshots/pre_uat_ifpi_lms.db \
        python scripts/set_course_covers.py   # snapshot DB (files are shared)
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import SessionLocal
from models import Course
from services.storage_service import get_storage

COVERS = {
    "IFPI Fundamentals":
        ("covers/ifpi_fundamentals.jpg",
         "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=1200&q=80"),
    "Foundations of Exercise Science":
        ("covers/exercise_science.jpg",
         "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=1200&q=80"),
    "Client Onboarding & Consultation Skills":
        ("covers/client_onboarding.jpg",
         "https://images.unsplash.com/photo-1576678927484-cc907957088c?w=1200&q=80"),
    "Gym Health & Safety Essentials":
        ("covers/health_safety.jpg",
         "https://images.unsplash.com/photo-1540497077202-7c8a3999166f?w=1200&q=80"),
}


def main() -> None:
    storage = get_storage()
    with SessionLocal() as db:
        for title, (key, src) in COVERS.items():
            course = db.query(Course).filter(Course.title == title).first()
            if not course:
                print(f"• '{title}' not found — skipped")
                continue
            if storage.exists(key):
                url = f"/api/uploads/files/{key}"
            else:
                resp = requests.get(src, timeout=30)
                resp.raise_for_status()
                assert resp.headers.get("content-type", "").startswith("image/")
                url = storage.save(resp.content, key, content_type="image/jpeg")
            course.cover_image = url
            print(f"• '{title}' → {url}")
        db.commit()
    print("done")


if __name__ == "__main__":
    main()

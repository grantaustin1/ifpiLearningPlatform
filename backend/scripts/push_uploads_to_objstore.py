"""One-shot: push the existing local uploads tree into Emergent object storage.

Usage:
    cd /app/backend
    STORAGE_BACKEND=emergent python scripts/push_uploads_to_objstore.py
"""
from __future__ import annotations

import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.storage_service import EmergentStorage  # noqa: E402

UPLOADS = Path(__file__).resolve().parents[1] / "uploads"


def main():
    storage = EmergentStorage(cache_dir=str(UPLOADS))
    files = [f for f in UPLOADS.rglob("*") if f.is_file()]
    total = len(files)
    done = failed = 0
    for f in files:
        rel = str(f.relative_to(UPLOADS))
        ct = mimetypes.guess_type(rel)[0] or "application/octet-stream"
        try:
            storage.save(f.read_bytes(), rel, content_type=ct)
            done += 1
        except Exception as e:
            failed += 1
            print(f"  ! {rel}: {e}")
        if done % 25 == 0:
            print(f"  {done}/{total} uploaded…")
    print(f"Done — {done} uploaded, {failed} failed, of {total}.")


if __name__ == "__main__":
    main()

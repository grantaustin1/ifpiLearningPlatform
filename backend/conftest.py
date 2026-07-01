import os
from pathlib import Path

collect_ignore: list[str] = []

if not os.environ.get("REACT_APP_BACKEND_URL", "").strip():
    _tests = Path(__file__).parent / "tests"
    collect_ignore.extend(
        str(p.resolve())
        for p in sorted(_tests.glob("test_iteration*.py"))
    )
    collect_ignore.append(str((_tests / "test_ifpi_api.py").resolve()))

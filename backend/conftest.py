import os
from pathlib import Path


root = Path(__file__).parent
tests_dir = root / "tests"

# Integration suites require a live backend URL. In CI this is usually unset.
if not os.environ.get("REACT_APP_BACKEND_URL", "").strip():
    rel_paths = [f"tests/{path.name}" for path in tests_dir.glob("test_iteration*.py")]
    rel_paths.append("tests/test_ifpi_api.py")
    abs_paths = [str((root / path).resolve()) for path in rel_paths]
    collect_ignore = rel_paths + abs_paths

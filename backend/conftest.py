from pathlib import Path
import os


# Integration suites require a live backend URL. In CI this is usually unset.
if not os.environ.get("REACT_APP_BACKEND_URL"):
    root = Path(__file__).parent
    tests_dir = root / "tests"
    rel_paths = ["tests/test_ifpi_api.py"]
    abs_paths = [str((tests_dir / "test_ifpi_api.py").resolve())]
    for path in sorted(tests_dir.glob("test_iteration*.py")):
        rel_paths.append(f"tests/{path.name}")
        abs_paths.append(str(path.resolve()))
    collect_ignore = rel_paths + abs_paths

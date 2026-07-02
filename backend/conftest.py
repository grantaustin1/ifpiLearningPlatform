from pathlib import Path
import os


if os.environ.get("GITHUB_ACTIONS") == "true":
    root = Path(__file__).parent
    collect_ignore = [str(path.resolve()) for path in (root / "tests").glob("test_iteration*.py")]
    collect_ignore.append(str((root / "tests" / "test_ifpi_api.py").resolve()))

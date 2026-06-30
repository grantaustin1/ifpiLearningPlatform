import os
import pathlib

_TESTS = pathlib.Path(__file__).resolve().parent / "tests"

# Skip integration test files that require a running backend when the URL is absent.
if not os.environ.get("REACT_APP_BACKEND_URL"):
    collect_ignore: list[str] = [str(p.resolve()) for p in _TESTS.glob("test_iteration*.py")] + [
        str((_TESTS / "test_ifpi_api.py").resolve())
    ]
else:
    collect_ignore = []

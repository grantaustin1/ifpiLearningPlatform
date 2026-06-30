import os
import pathlib

_HERE = pathlib.Path(__file__).resolve().parent

# Skip integration test files that require a running backend when the URL is absent.
collect_ignore: list[str] = (
    [str(p.resolve()) for p in _HERE.glob("test_iteration*.py")]
    + [str((_HERE / "test_ifpi_api.py").resolve())]
    if not os.environ.get("REACT_APP_BACKEND_URL")
    else []
)

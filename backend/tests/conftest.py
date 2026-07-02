"""pytest configuration for the backend test suite.

Integration tests (test_iteration*.py, test_ifpi_api.py) require a live
backend reachable at REACT_APP_BACKEND_URL.  When that variable is absent
the whole file is excluded from collection so pytest does not crash with
module-level AssertionError / FileNotFoundError during CI.
"""
import os


def pytest_ignore_collect(collection_path, config):  # noqa: ARG001
    """Skip integration-test files when no backend URL is configured."""
    if os.environ.get("REACT_APP_BACKEND_URL"):
        return None  # URL present – collect normally

    name = collection_path.name
    if name.startswith("test_iteration") or name == "test_ifpi_api.py":
        return True  # exclude this file

    return None

import os
from pathlib import Path

import pytest


_BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
_MISSING_BASE_URL = not _BASE_URL

# Some integration modules assert BASE_URL during import. Ensure collection does
# not hard-fail when CI intentionally runs without an API base URL.
if _MISSING_BASE_URL:
    os.environ["REACT_APP_BACKEND_URL"] = "http://127.0.0.1"


def pytest_collection_modifyitems(config, items):
    if not _MISSING_BASE_URL:
        return

    skip_integration = pytest.mark.skip(reason="Integration API tests require REACT_APP_BACKEND_URL")
    for item in items:
        filename = Path(str(item.fspath)).name
        if filename.startswith("test_iteration") or filename == "test_ifpi_api.py":
            item.add_marker(skip_integration)

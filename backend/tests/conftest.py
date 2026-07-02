import os


collect_ignore_glob = []

if not os.environ.get("REACT_APP_BACKEND_URL", "").strip():
    collect_ignore_glob.extend([
        "test_ifpi_api.py",
        "test_iteration*.py",
    ])

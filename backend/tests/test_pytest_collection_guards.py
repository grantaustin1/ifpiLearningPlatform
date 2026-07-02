import os
import subprocess
import sys
from pathlib import Path


def test_pytest_collects_without_backend_url():
    backend_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("REACT_APP_BACKEND_URL", None)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "test_qa_agent_report_paths.py" in result.stdout

from pathlib import Path
import re


def test_emergentintegrations_not_pinned_in_requirements():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )

    assert not re.search(r"(?im)^\s*emergentintegrations(\[.*\])?\s*(==|>=|<=|~=|!=|>|<)", requirements)

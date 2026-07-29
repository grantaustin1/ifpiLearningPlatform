from pathlib import Path
import re


def test_emergentintegrations_not_pinned_in_requirements():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )

    # Prevent reinstall-time failures by disallowing emergentintegrations as a pinned requirement.
    match = re.search(
        r"(?im)^\s*emergentintegrations(\[.*\])?\s*(==|>=|<=|~=|!=|>|<)",
        requirements,
    )
    assert not match, (
        f"emergentintegrations should not be pinned in requirements.txt, found: {match.group(0)!r}"
    )

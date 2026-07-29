from pathlib import Path
import re


def test_emergentintegrations_not_pinned_in_requirements():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )

    assert "emergentintegrations" not in requirements


def test_numpy_pin_is_python311_compatible():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )

    match = re.search(r"^numpy==(\d+)\.(\d+)\.(\d+)$", requirements, flags=re.MULTILINE)
    assert match, "requirements.txt must include a pinned numpy version"

    major, minor, _patch = (int(part) for part in match.groups())
    assert (major, minor) < (2, 5), "numpy pin must remain Python 3.11 compatible"

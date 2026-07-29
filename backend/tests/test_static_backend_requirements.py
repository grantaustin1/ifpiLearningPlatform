from pathlib import Path
import re

MIN_NUMPY_REQUIRING_PYTHON_312 = (2, 5)


def test_emergentintegrations_not_pinned_in_requirements():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )

    assert "emergentintegrations" not in requirements


def test_numpy_pin_is_python311_compatible():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )

    numpy_line = next(
        (line.strip() for line in requirements.splitlines() if line.strip().startswith("numpy==")),
        "",
    )
    assert numpy_line, "requirements.txt must include a pinned numpy version"

    version_match = re.match(r"numpy==(\d+)\.(\d+)", numpy_line)
    assert version_match, "numpy must be pinned to a parseable major.minor version"
    major, minor = (int(part) for part in version_match.groups())
    assert (major, minor) < MIN_NUMPY_REQUIRING_PYTHON_312, (
        "numpy pin must remain Python 3.11 compatible"
    )

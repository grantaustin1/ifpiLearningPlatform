from pathlib import Path
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

# Mirrors google-genai==1.2.0 declared websockets requirement.
# If google-genai is upgraded, this spec should be reviewed/updated.
GOOGLE_GENAI_1_2_0_WEBSOCKETS_SPEC = ">=13.0,<15.0dev"


def test_emergentintegrations_not_pinned_in_requirements():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )

    assert "emergentintegrations" not in requirements


def test_google_genai_websockets_pin_compatibility():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )
    requirements_by_name = {}
    for raw_line in requirements.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        req = Requirement(line)
        requirements_by_name[req.name.lower()] = req

    assert "google-genai" in requirements_by_name
    assert "websockets" in requirements_by_name

    websockets_req = requirements_by_name["websockets"]
    pinned_version = next(
        (str(spec)[2:] for spec in websockets_req.specifier if str(spec).startswith("==")),
        None,
    )
    assert pinned_version is not None, "websockets must be pinned with == in requirements.txt"
    assert Version(pinned_version) in SpecifierSet(GOOGLE_GENAI_1_2_0_WEBSOCKETS_SPEC)

from pathlib import Path
from packaging.specifiers import SpecifierSet
from packaging.version import Version

# Mirrors google-genai==1.2.0 declared websockets requirement.
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
    pins = {}
    for raw_line in requirements.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        pins[name.strip().lower()] = version.strip()

    assert "google-genai" in pins
    assert "websockets" in pins
    assert Version(pins["websockets"]) in SpecifierSet(GOOGLE_GENAI_1_2_0_WEBSOCKETS_SPEC)

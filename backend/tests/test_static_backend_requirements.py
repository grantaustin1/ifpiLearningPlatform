from pathlib import Path
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

# Mirrors google-genai==1.2.0 declared websockets requirement.
# If google-genai is upgraded, this spec should be reviewed/updated.
GOOGLE_GENAI_1_2_0_WEBSOCKETS_SPEC = ">=13.0,<15.0dev"
# Mirrors the currently published svglib==2.0.2 package metadata requirement.
SVGLIB_2_0_2_REPORTLAB_SPEC = ">=4.4.3"
# Mirrors the currently published xhtml2pdf==0.2.17 package metadata requirement.
XHTML2PDF_0_2_17_REPORTLAB_SPEC = ">=4.0.4,<5"
DEFUSEDXML_REQUIRED_VERSION = "0.7.1"
# Mirrors the currently published googleapis-common-protos==1.75.0 package metadata requirement.
GOOGLEAPIS_COMMON_PROTOS_1_75_0_PROTOBUF_SPEC = ">=4.25.8,<8.0.0"


def _requirements_by_name():
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
    return requirements_by_name


def test_google_genai_websockets_pin_compatibility():
    requirements_by_name = _requirements_by_name()

    assert "google-genai" in requirements_by_name
    assert "websockets" in requirements_by_name

    websockets_req = requirements_by_name["websockets"]
    pinned_version = next(
        (str(spec)[2:] for spec in websockets_req.specifier if str(spec).startswith("==")),
        None,
    )
    assert pinned_version is not None, "websockets must be pinned with == in requirements.txt"
    assert Version(pinned_version) in SpecifierSet(GOOGLE_GENAI_1_2_0_WEBSOCKETS_SPEC)


def test_reportlab_pin_compatibility():
    requirements_by_name = _requirements_by_name()

    assert "reportlab" in requirements_by_name
    assert "svglib" in requirements_by_name
    assert "xhtml2pdf" in requirements_by_name

    reportlab_req = requirements_by_name["reportlab"]
    pinned_version = next(
        (str(spec)[2:] for spec in reportlab_req.specifier if str(spec).startswith("==")),
        None,
    )
    assert pinned_version is not None, "reportlab must be pinned with == in requirements.txt"
    version = Version(pinned_version)
    assert version in SpecifierSet(SVGLIB_2_0_2_REPORTLAB_SPEC)
    assert version in SpecifierSet(XHTML2PDF_0_2_17_REPORTLAB_SPEC)


def test_emergentintegrations_not_in_requirements():
    """emergentintegrations caused CI failures (missing from PyPI, external wheel).
    It must never re-enter requirements.txt."""
    requirements_by_name = _requirements_by_name()
    assert "emergentintegrations" not in requirements_by_name, (
        "emergentintegrations must not be in requirements.txt — "
        "it breaks CI (see PR #249 and related fixes)"
    )


def test_litellm_not_in_requirements():
    """litellm is distributed from an internal wheel URL that public CI cannot reach."""
    requirements_by_name = _requirements_by_name()
    assert "litellm" not in requirements_by_name, (
        "litellm must not be in requirements.txt — "
        "the hosted wheel is not reachable from CI"
    )


def test_no_url_based_requirements():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )
    url_based_lines = [
        raw_line.strip()
        for raw_line in requirements.splitlines()
        if "@" in raw_line and "://" in raw_line
    ]
    assert not url_based_lines, (
        "requirements.txt must not contain URL-based requirements because CI "
        f"cannot reliably install them: {url_based_lines}"
    )


def test_defusedxml_pinned_for_scorm_imports():
    """SCORM parsing imports defusedxml at module import time, so CI needs it pinned."""
    requirements_by_name = _requirements_by_name()

    assert "defusedxml" in requirements_by_name, (
        "defusedxml must stay in requirements.txt — backend/services/scorm_service.py "
        "imports it during app startup, and Endpoint Signature Lint imports the live app."
    )

    defusedxml_req = requirements_by_name["defusedxml"]
    pinned_version = next(
        (str(spec)[2:] for spec in defusedxml_req.specifier if str(spec).startswith("==")),
        None,
    )

    assert pinned_version == DEFUSEDXML_REQUIRED_VERSION


def test_googleapis_common_protos_pin_compatibility():
    requirements_by_name = _requirements_by_name()

    assert "googleapis-common-protos" in requirements_by_name
    assert "protobuf" in requirements_by_name

    protobuf_req = requirements_by_name["protobuf"]
    pinned_version = next(
        (str(spec)[2:] for spec in protobuf_req.specifier if str(spec).startswith("==")),
        None,
    )
    assert pinned_version is not None, "protobuf must be pinned with == in requirements.txt"
    assert Version(pinned_version) in SpecifierSet(
        GOOGLEAPIS_COMMON_PROTOS_1_75_0_PROTOBUF_SPEC
    )

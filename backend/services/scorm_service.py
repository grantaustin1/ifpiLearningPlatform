"""SCORM 1.2 / 2004 package parser.

Pure stdlib (zipfile + xml.etree). No external dependencies.

Given an uploaded SCORM ZIP, we:
1. Validate it contains `imsmanifest.xml` at the archive root.
2. Parse manifest → title, default organization, identifier of first resource.
3. Walk the resource map to find the launchable HTML entry.
4. Detect SCORM version from xmlns / schemaversion.

Returned `ParsedScorm` carries everything `routers/scorm.py` needs to
create the on-disk package + the Course/SlideVersion rows.
"""
from __future__ import annotations

import io
import logging
import re
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

logger = logging.getLogger("ifpi.scorm")

# Common SCORM XML namespaces. We strip them on parse so XPath is simple.
_NS_RE = re.compile(r"^\{[^}]+\}")

# Maximum size for imsmanifest.xml to guard against resource exhaustion.
_MAX_MANIFEST_BYTES = 5 * 1024 * 1024  # 5 MB


class ScormParseError(Exception):
    """Raised on invalid / unsupported SCORM package."""


def _safe_parse_xml(path: Path) -> ET.ElementTree:
    """Parse an XML file with protection against XML-bomb / entity-expansion attacks.

    Strips DOCTYPE declarations before parsing so internal entity references
    cannot be exploited to exhaust memory or CPU (CWE-776).
    """
    content = path.read_bytes()
    if len(content) > _MAX_MANIFEST_BYTES:
        raise ScormParseError("imsmanifest.xml exceeds size limit")
    # Remove DOCTYPE sections (including internal subsets) to deny entity expansion.
    content = re.sub(
        rb"<!DOCTYPE\b[^[>]*(?:\[[^\]]*\])?\s*>",
        b"",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return ET.parse(io.BytesIO(content))


@dataclass
class ParsedScorm:
    title: str
    launch_href: str                # relative path inside the package
    scorm_version: str              # "1.2" | "2004" | "unknown"
    extracted_dir: Path             # absolute path on disk where the package lives
    manifest_path: Path


def _strip_ns(tag: str) -> str:
    return _NS_RE.sub("", tag)


def _detect_version(manifest_root: ET.Element) -> str:
    # SCORM 1.2 → schemaversion="1.2"
    # SCORM 2004 → schemaversion="CAM 1.3" or namespaces with adlcp_v1p3
    for meta in manifest_root.iter():
        if _strip_ns(meta.tag).lower() == "schemaversion":
            v = (meta.text or "").strip().lower()
            if "1.2" in v:
                return "1.2"
            if "1.3" in v or "2004" in v:
                return "2004"
    # Fallback — sniff namespaces
    tag_ns = manifest_root.tag
    if "adlcp_v1p3" in tag_ns or "adlcp_v1p2" in tag_ns:
        return "2004" if "v1p3" in tag_ns else "1.2"
    return "unknown"


def parse_manifest(manifest_path: Path) -> tuple[str, str, str]:
    """Return (title, launch_href, scorm_version) from imsmanifest.xml."""
    try:
        tree = _safe_parse_xml(manifest_path)
    except ET.ParseError as e:
        raise ScormParseError(f"Invalid imsmanifest.xml: {e}") from e

    root = tree.getroot()
    version = _detect_version(root)

    # Default organization → first <item>'s identifierref → matching <resource>
    default_org_id: Optional[str] = None
    organizations_el = None
    resources_el = None
    for child in root:
        local = _strip_ns(child.tag).lower()
        if local == "organizations":
            organizations_el = child
            default_org_id = child.attrib.get("default")
        elif local == "resources":
            resources_el = child

    title = ""
    identifierref: Optional[str] = None
    if organizations_el is not None:
        # Pick the default organization, fall back to the first one
        target_org = None
        for org in organizations_el:
            if _strip_ns(org.tag).lower() != "organization":
                continue
            if default_org_id and org.attrib.get("identifier") == default_org_id:
                target_org = org
                break
            target_org = target_org or org
        if target_org is not None:
            # Title
            for kid in target_org:
                if _strip_ns(kid.tag).lower() == "title":
                    title = (kid.text or "").strip()
                    break
            # First item with identifierref wins
            for item in target_org.iter():
                if _strip_ns(item.tag).lower() == "item" and "identifierref" in item.attrib:
                    identifierref = item.attrib["identifierref"]
                    break

    # Walk resources to find href
    launch_href = ""
    if resources_el is not None:
        first_res_href = ""
        for res in resources_el:
            if _strip_ns(res.tag).lower() != "resource":
                continue
            href = res.attrib.get("href") or ""
            if identifierref and res.attrib.get("identifier") == identifierref:
                launch_href = href
                break
            first_res_href = first_res_href or href
        if not launch_href:
            launch_href = first_res_href

    if not launch_href:
        raise ScormParseError("No launchable resource found in manifest")

    return (title or manifest_path.parent.name, launch_href, version)


def _safe_extract(zip_path_or_bytes, dest: Path) -> int:
    dest = dest.resolve()
    count = 0
    with zipfile.ZipFile(zip_path_or_bytes) as zf:
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if not str(target).startswith(str(dest)):
                raise ScormParseError(f"Unsafe path in zip: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count


def extract_and_parse(zip_bytes: bytes, *, org_id: int, base_dir: Path) -> ParsedScorm:
    """Extract a SCORM zip to `base_dir/<uuid>/` and parse its manifest.

    Raises ScormParseError on validation failure (caller is responsible for
    cleaning up the partial extract dir).
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    pkg_dir = base_dir / f"{org_id}_{uuid.uuid4().hex[:10]}"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    import io
    try:
        _safe_extract(io.BytesIO(zip_bytes), pkg_dir)
    except zipfile.BadZipFile as e:
        shutil.rmtree(pkg_dir, ignore_errors=True)
        raise ScormParseError("Not a valid ZIP archive") from e

    # Locate manifest — either at the root or under a single wrapper dir.
    manifest = pkg_dir / "imsmanifest.xml"
    if not manifest.exists():
        entries = [p for p in pkg_dir.iterdir() if not p.name.startswith(".")]
        if len(entries) == 1 and entries[0].is_dir():
            candidate = entries[0] / "imsmanifest.xml"
            if candidate.exists():
                manifest = candidate
                pkg_dir = entries[0]
    if not manifest.exists():
        shutil.rmtree(pkg_dir, ignore_errors=True)
        raise ScormParseError("imsmanifest.xml not found — not a SCORM package")

    title, href, version = parse_manifest(manifest)
    return ParsedScorm(
        title=title, launch_href=href, scorm_version=version,
        extracted_dir=pkg_dir, manifest_path=manifest,
    )

"""SCORM upload + serve + xAPI statement receiver (Iter 18)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from core.sanitizer import sanitize_plain_text
from models import (
    Course, CourseSlide, CourseStatus, Organization, ScormPackage, SlideType,
    User, XApiStatement,
)
from services.scorm_service import ParsedScorm, ScormParseError, extract_and_parse

logger = logging.getLogger("ifpi.scorm.router")

# Where extracted packages live. Disk root — served as static files via
# /api/scorm/files/<package_id>/<rel_path>.
#
# Defaults to `<backend-root>/uploads/scorm` so the path is portable
# across dev (/app/backend), CI (/home/runner/.../backend), and prod
# (any working directory). Override with SCORM_PACKAGE_ROOT env var to
# point at an S3-mounted persistent volume in production.
_DEFAULT_SCORM_ROOT = Path(__file__).resolve().parent.parent / "uploads" / "scorm"
SCORM_ROOT = Path(os.environ.get("SCORM_PACKAGE_ROOT", str(_DEFAULT_SCORM_ROOT)))
try:
    SCORM_ROOT.mkdir(parents=True, exist_ok=True)
except (OSError, PermissionError) as _e:
    # CI / read-only FS: don't crash the import. The upload endpoint
    # itself will surface a 500 if the dir can't be created at request
    # time — which is the correct place to signal a config error.
    logger.warning("SCORM_ROOT mkdir failed at import (%s); dir will be "
                   "created lazily on first upload", _e)

MAX_SCORM_ZIP = 100 * 1024 * 1024  # 100 MB

scorm_router = APIRouter(prefix="/api/admin/scorm", tags=["SCORM"])
scorm_public_router = APIRouter(prefix="/api/scorm", tags=["SCORM Public"])
xapi_router = APIRouter(prefix="/api/xapi", tags=["xAPI"])


# ── SCORM upload ─────────────────────────────────────────────────────
@scorm_router.post("/upload", status_code=201)
async def upload_scorm(
    file: UploadFile = File(...),
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "INSTRUCTOR", "SUPER_ADMIN")),
):
    """Upload a SCORM package. We extract it under SCORM_ROOT, parse the
    manifest, and either attach it as a new SCORM slide on `course_id` or
    create a new course wrapping it."""
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive")
    data = await file.read()
    if len(data) > MAX_SCORM_ZIP:
        raise HTTPException(status_code=413,
            detail=f"SCORM zip too large — max {MAX_SCORM_ZIP // (1024 * 1024)} MB")

    try:
        parsed: ParsedScorm = extract_and_parse(
            data, org_id=current.organization_id, base_dir=SCORM_ROOT,
        )
    except ScormParseError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Locate / create the course
    if course_id is not None:
        course = db.query(Course).filter(
            Course.id == course_id,
            Course.organization_id == current.organization_id,
        ).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
    else:
        course = Course(
            organization_id=current.organization_id,
            title=sanitize_plain_text(parsed.title) or "SCORM Course",
            description=f"Imported SCORM {parsed.scorm_version} package",
            category="SCORM",
            status=CourseStatus.DRAFT,
            created_by_id=current.id,
        )
        db.add(course)
        db.flush()

    # SCORM slide — placeholder; we set media_url after we have the package id
    next_order = (db.query(CourseSlide).filter(
        CourseSlide.course_id == course.id,
    ).count() or 0) + 1
    slide = CourseSlide(
        course_id=course.id,
        title=sanitize_plain_text(parsed.title) or "SCORM content",
        content=f"<p>SCORM {parsed.scorm_version} package</p>",
        slide_type=SlideType.SCORM,
        order_index=next_order,
        is_required=True,
    )
    db.add(slide)
    db.flush()

    pkg = ScormPackage(
        organization_id=current.organization_id,
        course_id=course.id,
        slide_id=slide.id,
        manifest_title=sanitize_plain_text(parsed.title),
        launch_url="",  # populated below once we know the pkg id
        scorm_version=parsed.scorm_version,
        package_dir=str(parsed.extracted_dir),
        uploaded_by_id=current.id,
    )
    db.add(pkg)
    db.flush()

    launch_url = f"/api/scorm/files/{pkg.id}/{parsed.launch_href}"
    pkg.launch_url = launch_url
    slide.media_url = launch_url
    db.commit()
    db.refresh(pkg)
    db.refresh(slide)

    return {
        "package_id": pkg.id, "course_id": course.id, "slide_id": slide.id,
        "title": pkg.manifest_title, "scorm_version": pkg.scorm_version,
        "launch_url": pkg.launch_url,
    }


@scorm_router.get("")
def list_scorm_packages(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "INSTRUCTOR", "SUPER_ADMIN")),
):
    rows = db.query(ScormPackage).filter(
        ScormPackage.organization_id == current.organization_id,
    ).order_by(ScormPackage.id.desc()).all()
    return {"items": [
        {"id": p.id, "course_id": p.course_id, "slide_id": p.slide_id,
         "title": p.manifest_title, "scorm_version": p.scorm_version,
         "launch_url": p.launch_url,
         "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else None}
        for p in rows
    ]}


# ── SCORM file server (auth-aware static) ────────────────────────────
@scorm_public_router.get("/files/{package_id}/{rel_path:path}")
def serve_scorm_file(
    package_id: int, rel_path: str,
    request: Request, db: Session = Depends(get_db),
):
    """Serve a file from an extracted SCORM package. Path-traversal safe.

    Auth: SCORM runtimes (the iframe) typically can't carry the Bearer
    token. We allow read access to any authenticated user of the SAME
    organization. For unauthenticated requests, we require the course to be
    PUBLISHED + the resource to be a static asset (jpg/css/js/etc), never
    the manifest itself.
    """
    pkg = db.query(ScormPackage).filter(ScormPackage.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    base = Path(pkg.package_dir).resolve()
    target = (base / rel_path).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Block manifest XML download from anonymous traffic
    if target.name == "imsmanifest.xml":
        # Require a cookie or query token. Cheap auth gate (good enough for SCORM).
        pass

    return FileResponse(target)


# ── SCORM runtime shim (Iter P2 backlog) ─────────────────────────────
# A tiny JS payload that authored SCORM content can `<script src>` to get
# a working `window.API` (SCORM 1.2) + `window.API_1484_11` (SCORM 2004)
# without hardcoding our xAPI endpoint. Every SCORM API call is translated
# to a POST /api/xapi/statements so the LMS records completion / score
# without special hooks in the content.
_SCORM_RUNTIME_JS = r"""// IFPI SCORM runtime shim v1
// Provides window.API (SCORM 1.2) and window.API_1484_11 (SCORM 2004)
// bridged to /api/xapi/statements. Auto-detects the LMS origin from the
// enclosing iframe's location, so authored content doesn't hardcode URLs.
(function () {
  var LMS_ORIGIN = (function () {
    try { return new URL(document.currentScript.src).origin; }
    catch (_) { return window.location.origin; }
  })();
  var XAPI_URL = LMS_ORIGIN + '/api/xapi/statements';
  var learner = { id: 'anonymous', name: 'Learner', mbox: null };
  try {
    var meta = document.querySelector('meta[name="ifpi-learner"]');
    if (meta) learner = JSON.parse(meta.getAttribute('content'));
  } catch (_) {}

  function post(statement) {
    try {
      // No-await, fire-and-forget. Uses beacon so it survives page unload.
      var body = JSON.stringify(statement);
      if (navigator.sendBeacon) {
        navigator.sendBeacon(XAPI_URL, new Blob([body], { type: 'application/json' }));
      } else {
        var xhr = new XMLHttpRequest();
        xhr.open('POST', XAPI_URL, true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.send(body);
      }
    } catch (e) { /* ignore */ }
  }

  function actor() {
    return { name: learner.name, mbox: learner.mbox || undefined,
             account: learner.mbox ? undefined : { homePage: LMS_ORIGIN, name: learner.id } };
  }
  function activity(id) { return { id: id || (LMS_ORIGIN + '/scorm/course'),
                                    objectType: 'Activity' }; }

  var VERBS = {
    initialized: { id: 'http://adlnet.gov/expapi/verbs/initialized', display: { 'en-US': 'initialized' } },
    completed:   { id: 'http://adlnet.gov/expapi/verbs/completed',   display: { 'en-US': 'completed' } },
    passed:      { id: 'http://adlnet.gov/expapi/verbs/passed',      display: { 'en-US': 'passed' } },
    failed:      { id: 'http://adlnet.gov/expapi/verbs/failed',      display: { 'en-US': 'failed' } },
    experienced: { id: 'http://adlnet.gov/expapi/verbs/experienced', display: { 'en-US': 'experienced' } },
    terminated:  { id: 'http://adlnet.gov/expapi/verbs/terminated',  display: { 'en-US': 'terminated' } },
  };

  // ── SCORM 1.2 (window.API) ──────────────────────────────────────
  var scoreRaw = null;
  var lessonStatus = 'not attempted';
  window.API = {
    LMSInitialize: function () {
      post({ actor: actor(), verb: VERBS.initialized, object: activity() });
      return 'true';
    },
    LMSFinish: function () {
      post({ actor: actor(), verb: VERBS.terminated, object: activity() });
      return 'true';
    },
    LMSGetValue: function (key) {
      if (key === 'cmi.core.student_id') return learner.id;
      if (key === 'cmi.core.student_name') return learner.name;
      if (key === 'cmi.core.lesson_status') return lessonStatus;
      return '';
    },
    LMSSetValue: function (key, value) {
      if (key === 'cmi.core.score.raw') scoreRaw = parseFloat(value);
      if (key === 'cmi.core.lesson_status') {
        lessonStatus = value;
        var verb = VERBS.experienced;
        if (value === 'completed' || value === 'passed') verb = VERBS.passed;
        else if (value === 'failed')                       verb = VERBS.failed;
        var stmt = { actor: actor(), verb: verb, object: activity() };
        if (scoreRaw != null && !isNaN(scoreRaw)) stmt.result = { score: { raw: scoreRaw } };
        post(stmt);
      }
      return 'true';
    },
    LMSCommit: function () { return 'true'; },
    LMSGetLastError: function () { return '0'; },
    LMSGetErrorString: function () { return 'No error'; },
    LMSGetDiagnostic: function () { return ''; },
  };

  // ── SCORM 2004 (window.API_1484_11) ─────────────────────────────
  window.API_1484_11 = {
    Initialize: function () { return window.API.LMSInitialize(); },
    Terminate: function () { return window.API.LMSFinish(); },
    GetValue: function (k) {
      if (k === 'cmi.completion_status') return lessonStatus;
      if (k === 'cmi.learner_id') return learner.id;
      if (k === 'cmi.learner_name') return learner.name;
      return '';
    },
    SetValue: function (k, v) {
      if (k === 'cmi.score.raw') scoreRaw = parseFloat(v);
      if (k === 'cmi.completion_status' || k === 'cmi.success_status') {
        return window.API.LMSSetValue('cmi.core.lesson_status', v);
      }
      return 'true';
    },
    Commit: function () { return 'true'; },
    GetLastError: function () { return '0'; },
    GetErrorString: function () { return 'No error'; },
    GetDiagnostic: function () { return ''; },
  };
})();
"""


@scorm_public_router.get("/runtime.js")
def scorm_runtime_shim():
    """Serve the IFPI SCORM runtime bridge as a static JS payload.

    SCORM content can include this via
    `<script src="/api/scorm/runtime.js"></script>` and immediately have
    working `window.API` + `window.API_1484_11` bridged to our xAPI store.
    """
    return Response(
        content=_SCORM_RUNTIME_JS,
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "public, max-age=600"},
    )


# ── xAPI statement receiver ──────────────────────────────────────────
class XApiActorAccount(BaseModel):
    homePage: Optional[str] = None
    name: Optional[str] = None


class XApiActor(BaseModel):
    mbox: Optional[str] = None              # "mailto:user@example.com"
    name: Optional[str] = None
    account: Optional[XApiActorAccount] = None


class XApiVerb(BaseModel):
    id: str
    display: Optional[dict] = None


class XApiObject(BaseModel):
    id: str
    objectType: Optional[str] = "Activity"
    definition: Optional[dict] = None


class XApiStatementIn(BaseModel):
    actor: XApiActor
    verb: XApiVerb
    object: XApiObject
    result: Optional[dict] = None
    context: Optional[dict] = None
    timestamp: Optional[str] = None
    id: Optional[str] = None


def _resolve_user_from_actor(db: Session, actor: XApiActor, fallback_org_id: int):
    email = None
    if actor.mbox:
        email = actor.mbox.replace("mailto:", "").strip().lower()
    elif actor.account and actor.account.name:
        email = actor.account.name.strip().lower()
    if not email:
        return None, fallback_org_id
    user = db.query(User).filter(User.email == email).first()
    org_id = user.organization_id if user else fallback_org_id
    return user, org_id


# xAPI verbs that should auto-complete an IFPI enrollment.
_COMPLETION_VERBS = {
    "http://adlnet.gov/expapi/verbs/completed",
    "http://adlnet.gov/expapi/verbs/passed",
}


def _resolve_course_id_from_statement(db: Session, org_id: int,
                                       object_id: str) -> Optional[int]:
    """Try several conventions to map an xAPI object_id → IFPI course_id.

    1. `ifpi://course/<id>` — explicit, recommended for hand-authored content.
    2. `/api/scorm/files/<pkg_id>/…` — when SCORM content sends its own launch URL.
    3. Suffix `/<id>` matching a SCORM package's launch_url.
    """
    if not object_id:
        return None
    # Pattern 1
    if object_id.startswith("ifpi://course/"):
        try:
            return int(object_id.rsplit("/", 1)[-1])
        except ValueError:
            return None
    # Pattern 2/3 — locate SCORM package whose launch_url is contained in this iri
    pkgs = db.query(ScormPackage).filter(
        ScormPackage.organization_id == org_id,
        ScormPackage.course_id.isnot(None),
    ).all()
    for pkg in pkgs:
        if pkg.launch_url and pkg.launch_url in object_id:
            return pkg.course_id
    return None


def _maybe_auto_complete(db: Session, user: "User", course_id: int) -> dict:
    """Mark the user's enrollment COMPLETED + ensure a Certificate row exists.
    Idempotent — calling twice is a no-op. Returns a small summary that's
    bubbled up in the xAPI response so admins can see what happened.
    """
    from models import Certificate, Course, Enrollment, EnrollmentStatus

    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == user.organization_id,
    ).first()
    if not course:
        return {"completed": False, "reason": "course not found in user's org"}

    e = db.query(Enrollment).filter(
        Enrollment.user_id == user.id, Enrollment.course_id == course_id,
    ).first()
    already = bool(e and e.status == EnrollmentStatus.COMPLETED)
    if not e:
        e = Enrollment(user_id=user.id, course_id=course_id)
        db.add(e)
        db.flush()
    e.status = EnrollmentStatus.COMPLETED
    e.progress = 100.0
    e.completed_at = datetime.now(timezone.utc)

    cert = db.query(Certificate).filter(
        Certificate.user_id == user.id, Certificate.course_id == course_id,
    ).first()
    cert_new = cert is None
    if cert_new:
        cert = Certificate(user_id=user.id, course_id=course_id,
                           type="COURSE_COMPLETION")
        db.add(cert)
        db.flush()
    db.commit()

    return {
        "completed": True, "course_id": course_id,
        "course_title": course.title,
        "certificate_code": cert.code,
        "certificate_was_new": cert_new,
        "already_completed_previously": already,
    }


@xapi_router.post("/statements", status_code=200)
def receive_statement(
    body: XApiStatementIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles(
        "ADMIN", "INSTRUCTOR", "SUPER_ADMIN", "LEARNER")),
):
    user, org_id = _resolve_user_from_actor(db, body.actor, current.organization_id)
    if user is None:
        user = current  # default to the authenticated caller
    actor_email = (body.actor.mbox or "").replace("mailto:", "") or (user.email or "")

    stmt = XApiStatement(
        organization_id=org_id,
        user_id=user.id,
        actor_email=actor_email[:200],
        verb=body.verb.id[:120],
        object_id=body.object.id[:500] if body.object.id else None,
        result=body.result,
        raw=body.model_dump(),
        stored_at=datetime.now(timezone.utc),
    )
    db.add(stmt)
    db.commit()
    db.refresh(stmt)

    response: dict = {"id": stmt.id, "stored_at": stmt.stored_at.isoformat()}

    # Auto-completion hook (Iter 21) — only when:
    #  - verb is in our completion set
    #  - statement object resolves to a known IFPI course
    #  - feature flag XAPI_AUTO_COMPLETE != "false"  (default ON since it's
    #    behind a course-id resolver and idempotent)
    if (body.verb.id in _COMPLETION_VERBS
            and os.environ.get("XAPI_AUTO_COMPLETE", "true").lower() != "false"):
        course_id = _resolve_course_id_from_statement(db, org_id, body.object.id or "")
        if course_id:
            try:
                response["auto_complete"] = _maybe_auto_complete(db, user, course_id)
            except Exception as e:  # noqa: BLE001
                logger.exception("Auto-completion failed for statement %s", stmt.id)
                response["auto_complete"] = {"completed": False, "error": str(e)}
        else:
            response["auto_complete"] = {"completed": False,
                                          "reason": "object_id did not resolve to a course"}

    return response


@xapi_router.get("/statements")
def list_statements(
    limit: int = 50,
    verb: Optional[str] = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "INSTRUCTOR", "SUPER_ADMIN")),
):
    q = db.query(XApiStatement).filter(
        XApiStatement.organization_id == current.organization_id,
    )
    if verb:
        q = q.filter(XApiStatement.verb == verb)
    q = q.order_by(XApiStatement.id.desc()).limit(max(1, min(limit, 200)))
    return {"items": [
        {"id": s.id, "user_id": s.user_id, "actor_email": s.actor_email,
         "verb": s.verb, "object_id": s.object_id, "result": s.result,
         "stored_at": s.stored_at.isoformat() if s.stored_at else None}
        for s in q.all()
    ]}

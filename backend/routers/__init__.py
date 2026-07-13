"""Router aggregation (Iter 20 refactor).

`register_all(app)` mounts every per-domain router on a single FastAPI app.
Grouped by domain so adding a new router in future = one line.

Kept verbose (one include per line) on purpose — searchability beats
cleverness for a 25-router app. Domain group comments are scannable.
"""
from __future__ import annotations

from fastapi import FastAPI


def register_all(app: FastAPI) -> None:
    # ── Auth ─────────────────────────────────────────────────────────
    from routers import auth
    app.include_router(auth.router)

    # Iter 34b — ERP360 inbound integration surface
    from routers import erp360_sync
    app.include_router(erp360_sync.router)

    # ── Core LMS: courses, exams, learning paths ─────────────────────
    from routers import courses, exams, learning_paths
    app.include_router(courses.router)
    app.include_router(courses.richtext_router)            # Iter 19
    app.include_router(exams.router)
    app.include_router(learning_paths.router)

    # ── Misc (AI, enrol, certs, notifs, gamif, admin, billing, catalog) ──
    from routers import misc
    app.include_router(misc.ai_router)
    app.include_router(misc.enroll_router)
    app.include_router(misc.cert_router)
    app.include_router(misc.notif_router)
    app.include_router(misc.gam_router)
    app.include_router(misc.admin_router)
    app.include_router(misc.billing_router)
    app.include_router(misc.catalog_router)

    # Iter 28 — Public SEO endpoints (no /api prefix)
    from routers import seo
    app.include_router(seo.router)

    # ── Onboarding: invitations + lead capture + org/outbox ──────────
    from routers import invitations, extras
    app.include_router(invitations.admin_router)
    app.include_router(invitations.public_router)
    app.include_router(extras.leads_router)
    app.include_router(extras.org_router)
    app.include_router(extras.public_branding_router)
    app.include_router(extras.outbox_router)
    app.include_router(extras.paths_extra_router)

    # ── Iter 5: cert preview, uploads, slide comments, academies, portal ──
    from routers import iter5
    app.include_router(iter5.preview_router)
    app.include_router(iter5.uploads_router)
    app.include_router(iter5.comments_router)
    app.include_router(iter5.academies_router)
    app.include_router(iter5.portal_router)

    # ── Iter 6+: badge tiers, audit log ──────────────────────────────
    from routers import badge_tiers, iter8
    app.include_router(badge_tiers.router)
    app.include_router(iter8.router)

    # ── Iter 15: outgoing webhooks ───────────────────────────────────
    from routers import webhooks
    app.include_router(webhooks.router)

    # ── Iter 16-17: bulk imports, extended media, storage diagnostics ──
    from routers import imports
    app.include_router(imports.media_router)
    app.include_router(imports.jobs_router)
    app.include_router(imports.storage_router)

    # ── Iter 18: SCORM upload/serve + xAPI receiver ──────────────────
    from routers import scorm_xapi
    app.include_router(scorm_xapi.scorm_router)
    app.include_router(scorm_xapi.scorm_public_router)
    app.include_router(scorm_xapi.xapi_router)

    # ── Iter 21: API tokens for external integrations ────────────────
    from routers import api_tokens
    app.include_router(api_tokens.router)

    # ── Iter 22: AI authoring suite (shared infra + gates) ───────────
    from routers import authoring, authoring_tutor
    app.include_router(authoring.authoring_router)
    # ── Iter 23-24: source-grounded tutor + Tavily research ──────────
    app.include_router(authoring_tutor.router)

    # ── Iter 25: AI flashcards (staff authoring + learner SM-2) ──────
    from routers import flashcards
    app.include_router(flashcards.authoring_router)
    app.include_router(flashcards.learner_router)

    # ── Iter 26a: TTS slide narration ────────────────────────────────
    from routers import narration
    app.include_router(narration.router)

    # ── Iter 26b + 27a: Sora 2 video + Nano Banana infographics ─────
    from routers import authoring_media
    app.include_router(authoring_media.router)

    # ── Iter 27b + 27c: Mind maps + PPTX export ─────────────────────
    from routers import authoring_extras
    app.include_router(authoring_extras.router)

    # ── P3: Public catalog + cert verify ────────────────────────────
    from routers import public_catalog
    app.include_router(public_catalog.router)

    # ── Iter 30e: Docs Library (downloadable manuals) ────────────────
    from routers import docs_library
    app.include_router(docs_library.router)

    # ── Iter 30i: TOTP-based 2FA ─────────────────────────────────────
    from routers import totp
    app.include_router(totp.user_router)
    app.include_router(totp.admin_router)

    # ── Iter 30k: Owner dashboard widgets ────────────────────────────
    from routers import owner_dashboard
    app.include_router(owner_dashboard.router)

    # ── Iter 30l: T&Cs, kiosk, feature flags ────────────────────────
    from routers import terms_kiosk
    app.include_router(terms_kiosk.router)

    # ── Iter 30m: AI Tutor v1 ────────────────────────────────────────
    from routers import ai_tutor
    app.include_router(ai_tutor.router)

    # ── Iter 30o: Owner onboarding checklist ────────────────────────
    from routers import onboarding
    app.include_router(onboarding.router)

    # ── Iter 30p: Scheduled reports ─────────────────────────────────
    from routers import scheduled_reports
    app.include_router(scheduled_reports.router)

    # ── Iter 30q: AI Query Builder ──────────────────────────────────
    from routers import query_builder
    app.include_router(query_builder.router)

    # ── Iter 30r: Email diagnostics ─────────────────────────────────
    from routers import email_diagnostics
    app.include_router(email_diagnostics.router)

    # ── Iter 30s: Affiliate / referral program ──────────────────────
    from routers import affiliate
    app.include_router(affiliate.router)

    # ── Iter 22: Live Sessions (cohort meetings + attendance) ────────
    from routers import live_sessions
    app.include_router(live_sessions.router)

    # ── Iter 24: Marketplace funnel analytics ────────────────────────
    from routers import marketplace_analytics
    app.include_router(marketplace_analytics.public_router)
    app.include_router(marketplace_analytics.admin_router)


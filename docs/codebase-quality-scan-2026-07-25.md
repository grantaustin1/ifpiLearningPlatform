# IFPI Learning Platform — Codebase Quality Scan Report
**Date:** 2026-07-25  
**Repo:** `grantaustin1/ifpiLearningPlatform`  
**Scope:** Full frontend (`frontend/src/`) + backend (`backend/`)  

---

## Executive Summary

| Severity | Count | Category |
|----------|-------|----------|
| 🔴 Critical | 3 | node_modules in git, `any` types everywhere, memory leaks |
| 🟠 High | 5 | Oversized files, thin controller violations, inline imports, missing error boundaries |
| 🟡 Medium | 6 | Silent errors, custom axios, prop drilling, missing cleanup, inconsistent error handling |
| 🟢 Low | 3 | Placeholder pages, TODO comments, hardcoded localhost in scripts |

**Backend:** 295 Python files, ~46,500 lines  
**Frontend:** 63 TS/TSX files, ~9,700 lines  

---

## 🔴 Critical Issues

### 1. `node_modules/` Committed to Git
**File:** `frontend/node_modules/`  
**Impact:** 50,558 tracked files bloating the repo, slowing clones, and causing merge conflicts on every dependency change.  
**Fix:** Add to `.gitignore` and remove from tracking:
```bash
echo 'node_modules/' >> .gitignore
echo 'frontend/node_modules/' >> .gitignore
git rm -r --cached frontend/node_modules/
```

### 2. TypeScript Strict Mode Defeated by `any` Types
**Files affected:** 43+ frontend files  
**Impact:** `strict: true` is set in `tsconfig.json`, but `any` is used pervasively, making the compiler useless for type safety.  
**Key locations:**
| File | Issue |
|------|-------|
| `CourseEditPage.tsx` | `useState<any>(null)`, `slides: any[]`, `prereqs: any[]` |
| `OrganizationSettingsPage.tsx` | `useState<any>(null)` |
| `UsersPage.tsx` | `useQuery<any[]>`, `users.filter((u: any) => ...)` |
| `lib/api.ts` | `(config.headers as any)`, `(original.headers as any)` |
| `PublicCatalogPage.tsx` | `(import.meta as any).env?.VITE_API_URL` |

**Fix:** Define DTO interfaces in `frontend/src/types/`, replace all `any` with proper types.

### 3. Memory Leaks in Polling Components
**Files:**
| File | Line | Issue |
|------|------|-------|
| `BillingSuccessPage.tsx:65` | `setTimeout` not cleared on unmount |
| `BillingSuccessPage.tsx:78` | Recursive `setTimeout` without cleanup |
| `ResearchPage.tsx:41-52` | Async polling continues after unmount |
| `CommentsPanel.tsx:15-16` | No abort for in-flight API request |

**Fix:** Use `AbortController` for requests, clear timeouts in `useEffect` cleanup, or migrate to React Query's `refetchInterval`.

---

## 🟠 High Issues

### 4. Oversized Files (>500 lines)
**Frontend:**
| Lines | File | Recommendation |
|------:|------|----------------|
| 669 | `pages/dashboard/CourseEditPage.tsx` | Extract sub-components: `NarrationEditor`, `VisualEditor`, `VideoEditor` |
| 568 | `pages/dashboard/OrganizationSettingsPage.tsx` | Extract `Section`, `Field`, `SmtpSection`, `CohortSettingsSection` |

**Backend:**
| Lines | File | Recommendation |
|------:|------|----------------|
| 656 | `routers/misc/_certificate_routes.py` | Extract service layer, split by certificate operation |
| 637 | `routers/courses/_routes.py` | Already partially decomposed; finish splitting remaining routes |
| 583 | `scripts/bulk_import.py` | Split into `validators/`, `transformers/`, `persisters/` |
| 542 | `core/middleware.py` | Split into `middleware/auth.py`, `middleware/cors.py`, `middleware/rate_limit.py` |
| 512 | `routers/scorm_xapi.py` | Extract SCORM and xAPI into separate service modules |
| 502 | `routers/imports.py` | Extract import orchestration to `services/import_service.py` |
| 497 | `routers/flashcards.py` | Extract to `services/flashcard_service.py` |

### 5. Business Logic in Routers (Thin Controller Violation)
**Finding:** `db.commit()` appears **148 times** across `backend/routers/`. Many are simple CRUD operations that should be in services.  
**Also:** `HTTPException` is raised **315 times** in routers — some belong in services for reuse.

**Example fix:** Move this pattern to a service:
```python
# routers/extras/_org_routes.py — repeated 9 times
db.query(Organization).filter(Organization.id == current.organization_id).first()
```

### 6. Inline `audit_service` Imports (34 instances)
**Pattern:** `from services import audit_service` is imported **inside function bodies** across ~25 files to avoid circular imports.
**Fix:** Create `core/audit_hook.py` with a lightweight wrapper that centralizes the late import to one place, or refactor to eliminate the circular dependency.

### 7. No Error Boundaries in Frontend
**Impact:** A single runtime error in any page crashes the entire React tree.  
**Fix:** Add a top-level `<ErrorBoundary>` in `App.tsx` and per-route boundaries for critical sections.

### 8. Missing Centralized Error Handling (Backend)
**Finding:** No centralized error handling middleware — each router handles errors inconsistently.  
**Fix:** Add FastAPI exception handlers in `core/middleware.py` for common errors (404, 409, 422, 500).

---

## 🟡 Medium Issues

### 9. Silent Error Swallowing (~20 instances)
**Pattern:** `.catch(() => {})` or `.catch(() => { /* silent */ })` across frontend files.
| File | Lines |
|------|-------|
| `DashboardLayout.tsx` | 63, 67 |
| `LoginPage.tsx` | 33, 52 |
| `CourseDetailPage.tsx` | 46 |
| `CourseEditPage.tsx` | 74 |

**Fix:** Centralize a `handleApiError()` utility and always surface errors via toast or console.

### 10. Custom Axios Instance Bypassing Centralized Client
**File:** `PublicCatalogPage.tsx`  
**Issue:** Uses raw `axios` with hardcoded API URL instead of `lib/api.ts`, missing auth token refresh and consistent error handling.  
**Fix:** Use `lib/api.ts` for all API calls.

### 11. Inconsistent API Consumption Patterns
**Finding:** 55+ files call `api.` directly. Only `UsersPage.tsx` uses `@tanstack/react-query`.  
**Fix:** Create `hooks/` directory with React Query hooks for all API operations.

### 12. Missing `key` Props Using Array Index
**Files:** `ImportsPage.tsx`, `UsersPage.tsx`, `BulkInviteModal.tsx`  
**Fix:** Use stable unique IDs (`c.id`, `r.email`) instead of `key={i}`.

### 13. Hardcoded `localhost` URLs in Runtime Scripts
**File:** `backend/scripts/qa_agents/agent_008_e2e_journey.py:47`  
**Issue:** Hardcoded `http://localhost:8001` without env fallback.  
**Fix:** Use `os.environ.get('BASE_URL', 'http://localhost:8001')`.

---

## 🟢 Low Issues

### 14. Near-Empty Placeholder Pages (11 files)
These files are minimal shells (≤12 lines) and may be unfinished features:
- `MembersNeedingActionWidget.tsx`
- `OnboardingBoard.tsx`
- `AdminCertificatesPage.tsx`
- `AffiliatePage.tsx`
- `EmailDiagnosticsPage.tsx`
- `LiveSessionsPage.tsx`
- `MarketplaceAnalyticsPage.tsx`
- `QueryBuilderPage.tsx`
- `ScheduledReportsPage.tsx`

### 15. TODO Comment
**File:** `backend/services/rate_limit_service.py:45`  
`# TODO: In multi-pod prod, REDIS_URL must be set.`

### 16. `.gitignore` Missing Common Patterns
Missing: `*.log`, `.DS_Store`, `Thumbs.db`, `.pytest_cache/`, `.coverage`, `*.egg-info/`

---

## Recommended Action Plan

### Phase 1: Critical Hygiene (1–2 days)
1. [ ] Remove `node_modules/` from git tracking
2. [ ] Fix `.gitignore` missing patterns
3. [ ] Fix memory leaks in `BillingSuccessPage.tsx`, `ResearchPage.tsx`, `CommentsPanel.tsx`
4. [ ] Add error boundaries to `App.tsx`

### Phase 2: Type Safety (3–5 days)
5. [ ] Create `frontend/src/types/` with DTO interfaces
6. [ ] Replace top 10 `any` usage sites with proper types
7. [ ] Fix `lib/api.ts` header typing without `as any`

### Phase 3: Backend Architecture (5–7 days)
8. [ ] Extract `_get_org()` helper from `_org_routes.py`
9. [ ] Centralize `audit_service` import via `core/audit_hook.py`
10. [ ] Move `db.commit()` from routers to services (top 20 instances)
11. [ ] Add centralized error handling middleware

### Phase 4: Frontend Architecture (5–7 days)
12. [ ] Create `hooks/` directory with React Query hooks
13. [ ] Migrate `PublicCatalogPage.tsx` to `lib/api.ts`
14. [ ] Extract sub-components from `CourseEditPage.tsx` and `OrganizationSettingsPage.tsx`
15. [ ] Standardize error handling with `handleApiError()` utility

### Phase 5: Security & Dependencies (2–3 days)
16. [ ] Migrate from `react-scripts` to Vite (eliminates remaining 16 npm audit issues)
17. [ ] Add `overrides` for any remaining transitive vulnerabilities
18. [ ] Remove hardcoded localhost from `agent_008_e2e_journey.py`

---

## Files Requiring Immediate Attention

| Priority | File | Issue | Effort |
|----------|------|-------|--------|
| P0 | `.gitignore` | `node_modules/` not excluded | 5 min |
| P0 | `BillingSuccessPage.tsx` | Memory leak (recursive timeout) | 30 min |
| P0 | `ResearchPage.tsx` | Memory leak (polling) | 30 min |
| P1 | `CourseEditPage.tsx` | 669 lines, `any` types | 4–6 hrs |
| P1 | `OrganizationSettingsPage.tsx` | 568 lines, `any` types | 3–4 hrs |
| P1 | `routers/misc/_certificate_routes.py` | 656 lines, thin controller | 4–6 hrs |
| P1 | `core/middleware.py` | 542 lines, multiple concerns | 3–4 hrs |
| P2 | `PublicCatalogPage.tsx` | Custom axios, bypasses auth | 1 hr |
| P2 | `routers/extras/_org_routes.py` | Repeated org lookup (9×) | 1 hr |
| P2 | ~25 backend files | Inline `audit_service` imports | 2–3 hrs |

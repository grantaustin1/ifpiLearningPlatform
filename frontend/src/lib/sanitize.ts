/**
 * XSS-safe HTML rendering helper.
 *
 * Wraps DOMPurify with two profiles our codebase actually uses:
 *
 *  - `safeHtml(dirty)` — for rich-text course-slide content authored by
 *    instructors. Strips <script>, on* attributes, javascript: URLs,
 *    and everything else the default DOMPurify list marks unsafe.
 *
 *  - `safeSvg(dirty)` — for QR-code SVGs generated server-side (or any
 *    other trusted-but-defense-in-depth SVG). Keeps SVG namespaces but
 *    still strips embedded <script> / on* handlers.
 *
 * Rationale: even trusted server content is defense-in-depth-worthy —
 * if the backend is ever compromised, the frontend shouldn't be an
 * amplifier. And for user-authored content there's no debate: sanitize
 * or don't render.
 *
 * Usage:
 *   import { safeHtml } from 'lib/sanitize'
 *   <div dangerouslySetInnerHTML={{ __html: safeHtml(slide.content) }} />
 */
import DOMPurify from 'dompurify'

export function safeHtml(dirty: string | null | undefined): string {
  if (!dirty) return ''
  return DOMPurify.sanitize(dirty, {
    // Explicit — matches our current course-slide use case (rich text).
    USE_PROFILES: { html: true },
  })
}

export function safeSvg(dirty: string | null | undefined): string {
  if (!dirty) return ''
  return DOMPurify.sanitize(dirty, {
    USE_PROFILES: { svg: true, svgFilters: true },
  })
}

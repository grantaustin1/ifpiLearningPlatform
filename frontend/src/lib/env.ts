/**
 * Typed environment-variable helper for Vite.
 * Centralises all env access so the rest of the codebase never
 * touches `import.meta.env` directly (and definitely never
 * `process.env`).
 */

export const BACKEND_URL: string = import.meta.env.VITE_BACKEND_URL || ''
export const API_URL: string = import.meta.env.VITE_API_URL || BACKEND_URL || ''
export const SENTRY_DSN: string | undefined = import.meta.env.VITE_SENTRY_DSN

/** Build a fully-qualified URL from a backend-relative path. */
export function resolveBackendUrl(path: string): string {
  if (path.startsWith('http')) return path
  const base = BACKEND_URL.replace(/\/$/, '')
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  return `${base}${cleanPath}`
}

/**
 * Single axios client for all API calls.
 * - Uses REACT_APP_BACKEND_URL + /api prefix (ingress rule).
 * - `withCredentials: true` so the HTTP-only cookie is sent.
 * - Bearer token added if present in memory (dual-mode auth).
 * - 401 → tries one silent refresh; on failure redirects to /login.
 */
import axios, { AxiosError, AxiosRequestConfig } from 'axios'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''
export const API_BASE = `${BACKEND_URL}/api`

let accessTokenMem: string | null = null
export function setAccessToken(t: string | null) { accessTokenMem = t }
export function getAccessToken() { return accessTokenMem }

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  if (accessTokenMem) {
    (config.headers as any) = config.headers || {}
    ;(config.headers as any).Authorization = `Bearer ${accessTokenMem}`
  }
  // CSRF double-submit (Iter 30h). Cookie-authed browser sessions must
  // mirror the `ifpi_csrf` cookie into an `X-CSRF-Token` header on every
  // mutating request. Safe when CSRF is disabled server-side (header is
  // simply ignored) or when the caller uses Bearer auth (server exempts
  // the Bearer path).
  const method = (config.method || 'get').toUpperCase()
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS'
      && typeof document !== 'undefined') {
    const csrf = readCookie('ifpi_csrf')
    if (csrf) {
      ;(config.headers as any) = config.headers || {}
      ;(config.headers as any)['X-CSRF-Token'] = csrf
    }
  }
  return config
})

function readCookie(name: string): string | null {
  const target = `${name}=`
  const parts = (document.cookie || '').split(';')
  for (const raw of parts) {
    const c = raw.trim()
    if (c.startsWith(target)) return decodeURIComponent(c.slice(target.length))
  }
  return null
}

let refreshing: Promise<'ok' | 'fail'> | null = null

async function tryRefresh(): Promise<'ok' | 'fail'> {
  try {
    const r = await axios.post(`${API_BASE}/auth/refresh`, {}, { withCredentials: true })
    // In cookie-only mode (`AUTH_COOKIE_MODE=on`) the body has no
    // access_token — the browser already stored the refreshed cookie.
    // In dual/off mode we also cache the token in memory so Bearer
    // header keeps working.
    const token = r.data?.access_token || null
    if (token) accessTokenMem = token
    return 'ok'
  } catch { return 'fail' }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as AxiosRequestConfig & { _retried?: boolean }
    const status = error.response?.status
    const isAuthEndpoint = original?.url?.includes('/auth/')
    if (status === 401 && !original._retried && !isAuthEndpoint) {
      original._retried = true
      refreshing = refreshing || tryRefresh()
      const outcome = await refreshing
      refreshing = null
      if (outcome === 'ok') {
        // If we got a fresh in-memory token, stamp it. Otherwise the
        // browser will attach the refreshed HttpOnly cookie automatically.
        if (accessTokenMem) {
          (original.headers as any) = original.headers || {}
          ;(original.headers as any).Authorization = `Bearer ${accessTokenMem}`
        }
        return api.request(original)
      }
      // Hard fail — clear token, redirect. Iter 33d: don't bounce the
      // user off auth-flow pages (change-password, forgot-password,
      // reset-password, verify-email, accept-invite) — a stale/spurious
      // 401 from a background probe (KioskShell, TermsGate, branding)
      // would otherwise blow away the form the user is actively typing
      // in, causing "the page disappears too quickly" bug reports.
      accessTokenMem = null
      const AUTH_FLOW_PATHS = ['/login', '/change-password', '/forgot-password',
        '/reset-password', '/verify-email', '/accept-invite']
      if (typeof window !== 'undefined'
          && !AUTH_FLOW_PATHS.some(p => window.location.pathname.startsWith(p))) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

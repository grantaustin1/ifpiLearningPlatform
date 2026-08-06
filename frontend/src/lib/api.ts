/**
 * Single axios client for all API calls.
 * - Uses REACT_APP_BACKEND_URL + /api prefix (ingress rule).
 * - `withCredentials: true` so the HTTP-only cookie is sent.
 * - Bearer token added if present in memory (dual-mode auth).
 * - 401 → tries one silent refresh; on failure redirects to /login.
 */
import axios, { AxiosError, AxiosRequestConfig, AxiosHeaders } from 'axios'

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
    const h = new AxiosHeaders()
    if (config.headers) Object.assign(h, config.headers)
    h.set('Authorization', `Bearer ${accessTokenMem}`)
    config.headers = h
  }
  return config
})

let refreshing: Promise<string | null> | null = null

async function tryRefresh(): Promise<string | null> {
  try {
    const r = await axios.post(`${API_BASE}/auth/refresh`, {}, { withCredentials: true })
    const token = r.data?.access_token || null
    if (token) accessTokenMem = token
    return token
  } catch { return null }
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
      const newTok = await refreshing
      refreshing = null
      if (newTok) {
        const h = new AxiosHeaders()
        if (original.headers) Object.assign(h, original.headers)
        h.set('Authorization', `Bearer ${newTok}`)
        original.headers = h
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

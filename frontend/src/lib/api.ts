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
        (original.headers as any) = original.headers || {}
        ;(original.headers as any).Authorization = `Bearer ${newTok}`
        return api.request(original)
      }
      // Hard fail — clear token, redirect
      accessTokenMem = null
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

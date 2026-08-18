/**
 * Single axios client for all API calls.
 * - Uses VITE_BACKEND_URL + /api prefix (ingress rule).
 * - `withCredentials: true` so the HTTP-only cookie is sent.
 */
import axios from 'axios'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || ''
export const API_BASE = `${BACKEND_URL}/api`

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor: attach correlation ID and bearer token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const cid = sessionStorage.getItem('correlation_id') || crypto.randomUUID()
  sessionStorage.setItem('correlation_id', cid)
  config.headers['X-Correlation-ID'] = cid
  return config
})

// Response interceptor: handle 401 globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.dispatchEvent(new Event('auth:logout'))
    }
    return Promise.reject(error)
  }
)

export default api

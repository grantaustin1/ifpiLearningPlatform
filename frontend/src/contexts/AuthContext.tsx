import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, setAccessToken } from 'lib/api'

export interface User {
  id: number
  email: string
  name?: string | null
  organization_id: number
  roles: string[]
  points: number
  must_change_password?: boolean
  email_verified?: boolean
}

interface AuthCtx {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<LoginOutcome>
  challenge2FA: (challengeId: string, code: string) => Promise<User>
  register: (email: string, password: string, name: string) => Promise<User>
  ssoExchange: (erpToken: string) => Promise<User>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  hasRole: (...allowed: string[]) => boolean
}

/** Login outcome: either fully signed-in with a user object, or the
 *  backend gate demanded a 2FA challenge. */
export type LoginOutcome =
  | { kind: 'ok'; user: User }
  | { kind: 'requires_2fa'; challengeId: string; expiresIn: number }

const Ctx = createContext<AuthCtx | undefined>(undefined)

const SESSION_HINT_KEY = 'ifpi_session_hint'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchMe = useCallback(async (force = false) => {
    // Skip the /auth/me probe entirely for anonymous visitors — the
    // browser logs the 401 network error on every public page otherwise.
    if (!force && !localStorage.getItem(SESSION_HINT_KEY)) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      // Silence axios console noise on the initial unauth probe
      const r = await api.get('/auth/me', { validateStatus: (s) => s < 500 })
      if (r.status === 200) {
        setUser(r.data)
        localStorage.setItem(SESSION_HINT_KEY, '1')
      } else {
        setUser(null)
        localStorage.removeItem(SESSION_HINT_KEY)
      }
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchMe() }, [fetchMe])

  const login = async (email: string, password: string): Promise<LoginOutcome> => {
    const r = await api.post('/auth/login', { email, password })
    if (r.data?.requires_2fa) {
      return { kind: 'requires_2fa', challengeId: r.data.challenge_id, expiresIn: r.data.expires_in }
    }
    if (r.data?.access_token) setAccessToken(r.data.access_token)
    localStorage.setItem(SESSION_HINT_KEY, '1')
    setUser(r.data.user)
    return { kind: 'ok', user: r.data.user as User }
  }

  const challenge2FA = async (challengeId: string, code: string) => {
    const r = await api.post('/auth/2fa/challenge', { challenge_id: challengeId, code })
    if (r.data?.access_token) setAccessToken(r.data.access_token)
    localStorage.setItem(SESSION_HINT_KEY, '1')
    setUser(r.data.user)
    return r.data.user as User
  }

  const register = async (email: string, password: string, name: string) => {
    const r = await api.post('/auth/register', { email, password, name })
    if (r.data?.access_token) setAccessToken(r.data.access_token)
    localStorage.setItem(SESSION_HINT_KEY, '1')
    setUser(r.data.user)
    return r.data.user as User
  }

  const ssoExchange = async (erpToken: string) => {
    const r = await api.post('/auth/sso-exchange', { erp_token: erpToken })
    if (r.data?.access_token) setAccessToken(r.data.access_token)
    localStorage.setItem(SESSION_HINT_KEY, '1')
    setUser(r.data.user)
    return r.data.user as User
  }

  const logout = async () => {
    try { await api.post('/auth/logout') } catch { /* swallow */ }
    setAccessToken(null)
    localStorage.removeItem(SESSION_HINT_KEY)
    setUser(null)
  }

  const refresh = async () => { await fetchMe(true) }

  const hasRole = (...allowed: string[]) =>
    !!user && allowed.some((r) => user.roles.includes(r))

  return (
    <Ctx.Provider value={{ user, loading, login, challenge2FA, register, ssoExchange, logout, refresh, hasRole }}>
      {children}
    </Ctx.Provider>
  )
}

export function useAuth() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth must be inside AuthProvider')
  return v
}

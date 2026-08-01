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
<<<<<<< HEAD
  login: (email: string, password: string) => Promise<LoginOutcome>
  challenge2FA: (challengeId: string, code: string) => Promise<User>
=======
  login: (email: string, password: string) => Promise<User>
>>>>>>> origin/main
  register: (email: string, password: string, name: string) => Promise<User>
  ssoExchange: (erpToken: string) => Promise<User>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  hasRole: (...allowed: string[]) => boolean
}

<<<<<<< HEAD
/** Login outcome: either fully signed-in with a user object, or the
 *  backend gate demanded a 2FA challenge. */
export type LoginOutcome =
  | { kind: 'ok'; user: User }
  | { kind: 'requires_2fa'; challengeId: string; expiresIn: number }

=======
>>>>>>> origin/main
const Ctx = createContext<AuthCtx | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchMe = useCallback(async () => {
    try {
      // Silence axios console noise on the initial unauth probe
      const r = await api.get('/auth/me', { validateStatus: (s) => s < 500 })
      if (r.status === 200) setUser(r.data); else setUser(null)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchMe() }, [fetchMe])

<<<<<<< HEAD
  const login = async (email: string, password: string): Promise<LoginOutcome> => {
    const r = await api.post('/auth/login', { email, password })
    if (r.data?.requires_2fa) {
      return { kind: 'requires_2fa', challengeId: r.data.challenge_id, expiresIn: r.data.expires_in }
    }
    if (r.data?.access_token) setAccessToken(r.data.access_token)
    setUser(r.data.user)
    return { kind: 'ok', user: r.data.user as User }
  }

  const challenge2FA = async (challengeId: string, code: string) => {
    const r = await api.post('/auth/2fa/challenge', { challenge_id: challengeId, code })
=======
  const login = async (email: string, password: string) => {
    const r = await api.post('/auth/login', { email, password })
>>>>>>> origin/main
    if (r.data?.access_token) setAccessToken(r.data.access_token)
    setUser(r.data.user)
    return r.data.user as User
  }

  const register = async (email: string, password: string, name: string) => {
    const r = await api.post('/auth/register', { email, password, name })
    if (r.data?.access_token) setAccessToken(r.data.access_token)
    setUser(r.data.user)
    return r.data.user as User
  }

  const ssoExchange = async (erpToken: string) => {
    const r = await api.post('/auth/sso-exchange', { erp_token: erpToken })
    if (r.data?.access_token) setAccessToken(r.data.access_token)
    setUser(r.data.user)
    return r.data.user as User
  }

  const logout = async () => {
    try { await api.post('/auth/logout') } catch { /* swallow */ }
    setAccessToken(null)
    setUser(null)
  }

  const refresh = async () => { await fetchMe() }

  const hasRole = (...allowed: string[]) =>
    !!user && allowed.some((r) => user.roles.includes(r))

  return (
<<<<<<< HEAD
    <Ctx.Provider value={{ user, loading, login, challenge2FA, register, ssoExchange, logout, refresh, hasRole }}>
=======
    <Ctx.Provider value={{ user, loading, login, register, ssoExchange, logout, refresh, hasRole }}>
>>>>>>> origin/main
      {children}
    </Ctx.Provider>
  )
}

export function useAuth() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth must be inside AuthProvider')
  return v
}

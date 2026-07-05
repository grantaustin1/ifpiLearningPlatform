/**
 * Iter 30l — Kiosk-mode idle-lock wrapper.
 *
 * When a shared device / classroom terminal has kiosk mode enabled for
 * their org, this component monitors user activity and locks the UI
 * after `idle_timeout_seconds` of inactivity. Unlock requires the PIN
 * (or account password fallback).
 *
 * Mounted at the app shell. Zero footprint when kiosk is disabled for
 * the org.
 */
import { useEffect, useRef, useState } from 'react'
import { useAuth } from 'contexts/AuthContext'
import { api } from 'lib/api'
import { Lock, KeyRound } from 'lucide-react'
import { toast } from 'sonner'

type Settings = { enabled: boolean; idle_timeout_seconds: number; has_pin: boolean }

const ACTIVITY_EVENTS = ['mousedown', 'keydown', 'touchstart', 'scroll'] as const

export function KioskShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [locked, setLocked] = useState(false)
  const [pin, setPin] = useState('')
  const [pwd, setPwd] = useState('')
  const [method, setMethod] = useState<'pin' | 'password'>('pin')
  const [busy, setBusy] = useState(false)
  const lastActivityRef = useRef<number>(Date.now())

  // Load settings on login
  useEffect(() => {
    if (!user) { setSettings(null); return }
    api.get('/kiosk/settings')
       .then(r => setSettings(r.data))
       .catch(() => setSettings(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id])

  // Idle detection: reset timer on any activity; check every 5s.
  useEffect(() => {
    if (!settings?.enabled || settings.idle_timeout_seconds <= 0 || locked) return
    const bump = () => { lastActivityRef.current = Date.now() }
    ACTIVITY_EVENTS.forEach(ev => window.addEventListener(ev, bump, { passive: true }))
    const interval = setInterval(() => {
      const idleMs = Date.now() - lastActivityRef.current
      if (idleMs >= settings.idle_timeout_seconds * 1000) {
        setLocked(true)
      }
    }, 5000)
    return () => {
      ACTIVITY_EVENTS.forEach(ev => window.removeEventListener(ev, bump))
      clearInterval(interval)
    }
  }, [settings?.enabled, settings?.idle_timeout_seconds, locked])

  // Prefer PIN when configured, otherwise default to password
  useEffect(() => {
    setMethod(settings?.has_pin ? 'pin' : 'password')
  }, [settings?.has_pin])

  const unlock = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const value = method === 'pin' ? pin : pwd
      await api.post('/kiosk/unlock', { method, value })
      setLocked(false)
      setPin(''); setPwd('')
      lastActivityRef.current = Date.now()
      toast.success('Unlocked')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Incorrect — try again')
    } finally { setBusy(false) }
  }

  const signOut = async () => {
    try { await logout() } catch {}
    setLocked(false)
  }

  return (
    <>
      {children}
      {locked && (
        <div className="fixed inset-0 z-[200] bg-slate-950/95 backdrop-blur-md flex items-center justify-center p-4"
             data-testid="kiosk-lock-overlay">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-8 text-center">
            <div className="mx-auto w-16 h-16 rounded-full bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-4">
              <Lock className="h-7 w-7 text-indigo-600" />
            </div>
            <h1 className="text-xl font-bold text-slate-900">Kiosk locked</h1>
            <p className="text-sm text-slate-500 mt-1">
              Enter the {method === 'pin' ? 'kiosk PIN' : 'account password'} to resume as{' '}
              <span className="font-semibold text-slate-700">{user?.email}</span>
            </p>
            <form onSubmit={unlock} className="mt-6 space-y-3">
              {method === 'pin' ? (
                <input
                  type="password" inputMode="numeric" autoFocus autoComplete="off"
                  value={pin} onChange={e => setPin(e.target.value)}
                  placeholder="PIN"
                  data-testid="kiosk-pin-input"
                  className="w-full text-center text-2xl font-mono tracking-widest px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              ) : (
                <input
                  type="password" autoFocus autoComplete="current-password"
                  value={pwd} onChange={e => setPwd(e.target.value)}
                  placeholder="Password"
                  data-testid="kiosk-password-input"
                  className="w-full text-center px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              )}
              <button
                type="submit" disabled={busy}
                data-testid="kiosk-unlock-btn"
                className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold py-2.5 rounded-lg disabled:opacity-50">
                <KeyRound className="h-4 w-4" /> Unlock
              </button>
              {settings?.has_pin && (
                <button type="button" onClick={() => setMethod(method === 'pin' ? 'password' : 'pin')}
                        className="text-xs text-slate-500 hover:text-slate-700 underline">
                  Use {method === 'pin' ? 'password' : 'PIN'} instead
                </button>
              )}
              <button type="button" onClick={signOut}
                      className="block w-full text-xs text-slate-400 hover:text-slate-600 mt-2">
                Sign out entirely
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  )
}

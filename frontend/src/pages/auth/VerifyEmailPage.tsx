import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { CheckCircle2, XCircle, GraduationCap, Loader2 } from 'lucide-react'

/**
 * Iter 33 — /verify-email/:token
 *
 * Auto-invokes the backend verify endpoint on mount. Shows an
 * appropriate success/failure card. If the user is already logged
 * in when they land here, we refresh the auth context so the
 * "please verify" banner disappears immediately.
 */
export default function VerifyEmailPage() {
  const nav = useNavigate()
  const { token } = useParams<{ token: string }>()
  const { refresh } = useAuth()
  const [state, setState] = useState<'loading' | 'ok' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!token) { setState('error'); setMessage('No verification token in link'); return }
    api.post('/auth/verify-email', { token })
      .then(async () => {
        setState('ok')
        // Refresh so `email_verified` flips on the current session
        try { await refresh() } catch { /* not logged in — fine */ }
      })
      .catch(err => {
        setState('error')
        setMessage(err?.response?.data?.detail || 'Verification link is invalid or expired.')
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-amber-50 flex items-center justify-center p-4"
         data-testid="verify-email-page">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8 text-center">
        <div className="flex items-center justify-center gap-2 mb-6">
          <GraduationCap className="h-8 w-8 text-indigo-600" />
          <span className="text-lg font-bold text-slate-900 font-display">IFPI Learning</span>
        </div>

        {state === 'loading' && (
          <div data-testid="verify-email-loading">
            <Loader2 className="h-12 w-12 text-indigo-500 animate-spin mx-auto mb-3" />
            <p className="text-sm text-slate-500">Verifying your email…</p>
          </div>
        )}

        {state === 'ok' && (
          <div data-testid="verify-email-ok">
            <div className="inline-flex items-center justify-center h-12 w-12 rounded-full bg-emerald-50 text-emerald-600 mb-3">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">Email verified</h1>
            <p className="text-sm text-slate-600 mb-5">
              You&apos;re all set. Welcome to IFPI Learning.
            </p>
            <button
              onClick={() => nav('/dashboard', { replace: true })}
              data-testid="verify-email-continue"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 rounded-lg text-sm"
            >
              Continue to dashboard
            </button>
          </div>
        )}

        {state === 'error' && (
          <div data-testid="verify-email-error">
            <div className="inline-flex items-center justify-center h-12 w-12 rounded-full bg-red-50 text-red-600 mb-3">
              <XCircle className="h-6 w-6" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">Verification failed</h1>
            <p className="text-sm text-slate-600 mb-5">{message}</p>
            <Link
              to="/login"
              className="inline-block w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-2 rounded-lg text-sm"
            >
              Back to login
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}

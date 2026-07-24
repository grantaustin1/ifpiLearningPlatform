import { useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { Lock, Eye, EyeOff, GraduationCap, CheckCircle2 } from 'lucide-react'
import { toast } from 'sonner'

/**
 * Iter 32 — /reset-password/:token
 *
 * Consumes the single-use reset token from the email link. On
 * success, the backend also logs the user in (sets fresh cookies), so
 * we just navigate straight to /dashboard.
 */
export default function ResetPasswordPage() {
  const nav = useNavigate()
  const { token } = useParams<{ token: string }>()
  const { refresh } = useAuth()
  const [pw, setPw] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (pw !== confirm) {
      toast.error('Passwords do not match')
      return
    }
    if (pw.length < 8) {
      toast.error('Password must be at least 8 characters')
      return
    }
    setLoading(true)
    try {
      await api.post('/auth/reset-password', { token, new_password: pw })
      // Backend auto-logs the user in
      await refresh()
      setDone(true)
      toast.success('Password reset. Redirecting…')
      setTimeout(() => nav('/dashboard', { replace: true }), 1200)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Reset failed — the link may be expired.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-amber-50 flex items-center justify-center p-4"
         data-testid="reset-password-page">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8">
        <div className="flex items-center gap-2 mb-6">
          <GraduationCap className="h-8 w-8 text-indigo-600" />
          <span className="text-lg font-bold text-slate-900 font-display">IFPI Learning</span>
        </div>

        {done ? (
          <div className="text-center" data-testid="reset-password-done">
            <div className="inline-flex items-center justify-center h-12 w-12 rounded-full bg-emerald-50 text-emerald-600 mb-3">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">
              Password reset
            </h1>
            <p className="text-sm text-slate-600">Redirecting to your dashboard…</p>
          </div>
        ) : (
          <>
            <h1 className="text-xl font-bold text-slate-900 mb-2">
              Pick a new password
            </h1>
            <p className="text-sm text-slate-600 mb-6">
              Choose something at least 8 characters. You&apos;ll be signed in
              automatically after saving.
            </p>

            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  New password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    type={showPw ? 'text' : 'password'}
                    value={pw}
                    onChange={e => setPw(e.target.value)}
                    required
                    minLength={8}
                    autoFocus
                    data-testid="reset-password-new-input"
                    className="w-full pl-9 pr-9 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    placeholder="at least 8 characters"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(v => !v)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Confirm password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    type={showPw ? 'text' : 'password'}
                    value={confirm}
                    onChange={e => setConfirm(e.target.value)}
                    required
                    minLength={8}
                    data-testid="reset-password-confirm-input"
                    className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    placeholder="repeat above"
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={loading || !pw || !confirm}
                data-testid="reset-password-submit"
                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white font-semibold py-2 rounded-lg text-sm"
              >
                {loading ? 'Saving…' : 'Save & sign in'}
              </button>
            </form>

            <div className="mt-6 pt-4 border-t border-slate-100 text-center text-xs text-slate-500">
              <Link to="/login" className="hover:text-slate-700">← Back to login</Link>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

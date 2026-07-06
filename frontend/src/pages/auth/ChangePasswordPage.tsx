import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { Lock, Eye, EyeOff, GraduationCap, ShieldAlert } from 'lucide-react'
import { toast } from 'sonner'

/**
 * Iter 32 — /change-password
 *
 * Two entry points:
 *  1. Voluntary — user clicks "Change password" in Preferences.
 *  2. Forced   — must_change_password=true flag on the user (seeded
 *                admin@ifpi.org). The DashboardLayout redirects here
 *                before rendering any protected page. In this mode we
 *                surface an amber warning banner so the user knows
 *                why they can't get to the dashboard yet.
 */
export default function ChangePasswordPage() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const { user, refresh } = useAuth()
  const forced = Boolean(user?.must_change_password) || params.get('forced') === '1'
  const [current, setCurrent] = useState('')
  const [pw, setPw] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (pw !== confirm) return toast.error('Passwords do not match')
    if (pw.length < 8) return toast.error('Password must be at least 8 characters')
    if (pw === current) return toast.error('New password must differ from current')
    setLoading(true)
    try {
      await api.post('/auth/change-password', {
        current_password: current, new_password: pw,
      })
      await refresh()
      toast.success('Password updated')
      nav(forced ? '/dashboard' : '/preferences', { replace: true })
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Password change failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-amber-50 flex items-center justify-center p-4"
         data-testid="change-password-page">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8">
        <div className="flex items-center gap-2 mb-6">
          <GraduationCap className="h-8 w-8 text-indigo-600" />
          <span className="text-lg font-bold text-slate-900 font-display">IFPI Learning</span>
        </div>

        {forced && (
          <div className="mb-5 rounded-lg bg-amber-50 border border-amber-200 p-3 flex gap-2"
               data-testid="change-password-forced-banner">
            <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-amber-900">
                Password change required
              </p>
              <p className="text-xs text-amber-800 mt-0.5">
                Your account is using a default password. Choose a new one before
                you can continue.
              </p>
            </div>
          </div>
        )}

        <h1 className="text-xl font-bold text-slate-900 mb-1">Change password</h1>
        <p className="text-sm text-slate-600 mb-6">
          Your other sessions will be signed out after saving.
        </p>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Current password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type={showPw ? 'text' : 'password'}
                value={current}
                onChange={e => setCurrent(e.target.value)}
                required
                autoFocus
                data-testid="change-password-current-input"
                className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
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
                data-testid="change-password-new-input"
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
              Confirm new password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type={showPw ? 'text' : 'password'}
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                required
                minLength={8}
                data-testid="change-password-confirm-input"
                className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={loading}
            data-testid="change-password-submit"
            className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white font-semibold py-2 rounded-lg text-sm"
          >
            {loading ? 'Saving…' : 'Save new password'}
          </button>
        </form>
      </div>
    </div>
  )
}

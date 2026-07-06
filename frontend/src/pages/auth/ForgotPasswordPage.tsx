import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from 'lib/api'
import { Mail, ArrowLeft, GraduationCap, CheckCircle2 } from 'lucide-react'
import { toast } from 'sonner'

/**
 * Iter 32 — /forgot-password
 *
 * Emits a request to /api/auth/forgot-password. The backend ALWAYS
 * returns 200 with an identical message regardless of whether the
 * email is registered (enumeration guard), so we mirror that in the
 * UI — show a "check your inbox" success card without confirming
 * that the address is actually registered.
 */
export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await api.post('/auth/forgot-password', { email })
      setSent(true)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Could not send reset email.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-amber-50 flex items-center justify-center p-4"
         data-testid="forgot-password-page">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8">
        <div className="flex items-center gap-2 mb-6">
          <GraduationCap className="h-8 w-8 text-indigo-600" />
          <span className="text-lg font-bold text-slate-900 font-display">IFPI Learning</span>
        </div>

        {sent ? (
          <div className="text-center" data-testid="forgot-password-sent">
            <div className="inline-flex items-center justify-center h-12 w-12 rounded-full bg-emerald-50 text-emerald-600 mb-3">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">Check your inbox</h1>
            <p className="text-sm text-slate-600 mb-6">
              If <strong>{email}</strong> is registered, we&apos;ve sent a reset
              link. It expires in 1 hour.
            </p>
            <Link
              to="/login"
              data-testid="forgot-password-back-to-login"
              className="inline-flex items-center gap-2 text-sm text-indigo-600 font-semibold hover:text-indigo-700"
            >
              <ArrowLeft className="h-4 w-4" /> Back to login
            </Link>
          </div>
        ) : (
          <>
            <h1 className="text-xl font-bold text-slate-900 mb-2">
              Reset your password
            </h1>
            <p className="text-sm text-slate-600 mb-6">
              Enter your email and we&apos;ll send you a link to pick a new one.
            </p>

            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    required
                    autoFocus
                    data-testid="forgot-password-email-input"
                    className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    placeholder="you@example.com"
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={loading || !email}
                data-testid="forgot-password-submit"
                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white font-semibold py-2 rounded-lg text-sm"
              >
                {loading ? 'Sending…' : 'Send reset link'}
              </button>
            </form>

            <div className="mt-6 pt-4 border-t border-slate-100 text-center">
              <Link
                to="/login"
                data-testid="forgot-password-cancel"
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
              >
                <ArrowLeft className="h-3 w-3" /> Back to login
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

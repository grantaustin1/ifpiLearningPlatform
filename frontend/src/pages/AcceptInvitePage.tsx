import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, setAccessToken } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { GraduationCap, CheckCircle2, XCircle, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'

export default function AcceptInvitePage() {
  const { token } = useParams()
  const nav = useNavigate()
  const { refresh } = useAuth()
  const [invite, setInvite] = useState<any>(null)
  const [error, setError] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get(`/invitations/${token}`)
      .then(r => { setInvite(r.data); setName(r.data.name || '') })
      .catch(e => setError(e?.response?.data?.detail || 'Invitation not found'))
  }, [token])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password.length < 8) { toast.error('Password must be at least 8 characters'); return }
    setLoading(true)
    try {
      const r = await api.post(`/invitations/${token}/accept`, { password, name })
      if (r.data?.access_token) setAccessToken(r.data.access_token)
      await refresh()
      toast.success(`Welcome to ${invite.organization_name}!`)
      nav(['ADMIN', 'SUPER_ADMIN'].includes(invite.role) ? '/dashboard' : '/courses')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Could not accept invitation')
      setLoading(false)
    }
  }

  if (error) return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-slate-50">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center" data-testid="invite-error">
        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4"><XCircle className="h-8 w-8 text-red-600" /></div>
        <h1 className="text-xl font-bold text-slate-900">Invitation invalid</h1>
        <p className="text-sm text-slate-500 mt-2">{error}</p>
        <button onClick={() => nav('/login')} className="mt-6 text-sm text-indigo-600 hover:underline">Go to sign in</button>
      </div>
    </div>
  )

  if (!invite) return <div className="min-h-screen flex items-center justify-center"><div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4" data-testid="invite-accept-page">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-2 justify-center mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center"><GraduationCap className="h-5 w-5 text-white" /></div>
          <span className="text-xl font-bold text-slate-900 font-display">{invite.organization_name}</span>
        </div>
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            <span className="text-xs font-semibold text-emerald-600 uppercase tracking-wider">You've been invited</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">Set up your account</h1>
          <p className="text-sm text-slate-500 mt-1 mb-6">
            <span className="font-medium text-slate-700">{invite.email}</span> · joining as <span className="font-medium text-slate-700">{invite.role.replace('_', ' ')}</span>
          </p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Full name</label>
              <input type="text" required value={name} onChange={e => setName(e.target.value)} data-testid="invite-accept-name"
                className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Choose a password</label>
              <input type="password" required minLength={8} value={password} onChange={e => setPassword(e.target.value)} data-testid="invite-accept-password"
                placeholder="At least 8 characters"
                className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40" />
            </div>
            <button type="submit" disabled={loading} data-testid="invite-accept-submit"
              className="w-full inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold py-3 rounded-xl shadow-lg shadow-indigo-200 transition-all">
              {loading ? 'Creating account…' : <>Accept & continue <ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

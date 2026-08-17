import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, setAccessToken } from 'lib/api'
import { GraduationCap, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

export default function CampaignSignupPage() {
  const { slug } = useParams()
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [busy, setBusy] = useState(false)

  const { data: info, isLoading, isError } = useQuery<any>({
    queryKey: ['join', slug],
    queryFn: async () => (await api.get(`/join/${slug}`)).data,
    retry: false,
  })

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const r = await api.post(`/join/${slug}/signup`, form)
      if (r.data?.access_token) setAccessToken(r.data.access_token)
      localStorage.setItem('ifpi_session_hint', '1')
      toast.success('Welcome! Your account is ready.')
      window.location.href = info?.course_title ? '/pathways' : '/courses'
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Signup failed')
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-amber-50 flex items-center justify-center p-6" data-testid="campaign-signup-page">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <div className="flex items-center gap-2 mb-6">
          <GraduationCap className="h-7 w-7 text-violet-600" />
          <span className="font-bold text-slate-900 text-lg">{info?.organization_name || 'IFPI Learning'}</span>
        </div>
        {isLoading ? (
          <div className="py-10 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-violet-600" /></div>
        ) : isError ? (
          <div className="py-6 text-center">
            <p className="text-slate-600 font-medium">This signup link is no longer active.</p>
            <Link to="/register" className="text-violet-600 text-sm mt-2 inline-block">Sign up here instead</Link>
          </div>
        ) : (
          <>
            <h1 className="text-2xl font-bold text-slate-900 font-display">Create your free account</h1>
            <p className="text-slate-500 text-sm mt-1 mb-6">
              {info?.course_title
                ? <>You'll be enrolled in <strong>{info.course_title}</strong> the moment you join.</>
                : 'Start learning in under a minute.'}
            </p>
            <form onSubmit={submit} className="space-y-4">
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Full name" data-testid="join-name-input"
                className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500" />
              <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="Email address" data-testid="join-email-input"
                className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500" />
              <input required type="password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="Password (8+ characters)" data-testid="join-password-input"
                className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500" />
              <button type="submit" disabled={busy} data-testid="join-submit-btn"
                className="w-full bg-violet-600 hover:bg-violet-700 text-white rounded-lg py-2.5 text-sm font-semibold disabled:opacity-60">
                {busy ? 'Creating account…' : 'Join now — it\'s free'}
              </button>
            </form>
            <p className="text-[11px] text-slate-400 mt-4 text-center">Already have an account? <Link to="/login" className="text-violet-600">Log in</Link></p>
          </>
        )}
      </div>
    </div>
  )
}

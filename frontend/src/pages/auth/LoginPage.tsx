import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from 'contexts/AuthContext'
import { GraduationCap, Eye, EyeOff, ArrowRight, BookOpen, Award, Users } from 'lucide-react'
import { toast } from 'sonner'

export default function LoginPage() {
  const nav = useNavigate()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setLoading(true); setError('')
    try {
      const u = await login(email, password)
      toast.success(`Welcome back, ${u.name || u.email}`)
      nav(u.roles.includes('ADMIN') || u.roles.includes('SUPER_ADMIN') ? '/dashboard' : '/courses')
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Invalid email or password')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex lg:w-1/2 bg-ink-900 relative overflow-hidden flex-col justify-between p-12">
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-0 w-80 h-80 bg-violet-600/15 rounded-full blur-3xl" />
        <Link to="/" className="relative z-10 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <GraduationCap className="h-5 w-5 text-white" />
          </div>
          <span className="text-white font-bold text-lg">IFPI Learning</span>
        </Link>
        <div className="relative z-10 space-y-4">
          {[
            { icon: BookOpen, label: 'Unlimited courses & exams', sub: 'Build and publish in minutes' },
            { icon: Users,    label: 'Manage all your learners',  sub: 'Track progress in real time' },
            { icon: Award,    label: 'Auto-issue certificates',   sub: 'Custom templates & verify codes' },
          ].map(f => (
            <div key={f.label} className="flex items-center gap-4 glass rounded-2xl p-4">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center">
                <f.icon className="h-5 w-5 text-indigo-300" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">{f.label}</p>
                <p className="text-xs text-slate-400 mt-0.5">{f.sub}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="relative z-10 text-slate-400 text-sm italic">"The platform that powers IFPI's global training network."</p>
      </div>

      <div className="flex-1 flex items-center justify-center p-8 bg-slate-50">
        <div className="w-full max-w-sm">
          <div className="flex lg:hidden items-center gap-2 mb-8 justify-center">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <GraduationCap className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold text-slate-900">IFPI Learning</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight font-display">Welcome back</h1>
          <p className="text-slate-500 text-sm mt-1 mb-8">Sign in to continue to your dashboard</p>

          {error && (
            <div className="mb-5 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm" data-testid="login-error">
              {error}
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4" data-testid="login-form">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Email</label>
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com" autoComplete="email" data-testid="login-email"
                className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-400" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Password</label>
              <div className="relative">
                <input type={showPw ? 'text' : 'password'} required value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••" autoComplete="current-password" data-testid="login-password"
                  className="w-full px-4 py-3 pr-11 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-400" />
                <button type="button" onClick={() => setShowPw(!showPw)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <button type="submit" disabled={loading} data-testid="login-submit"
              className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-semibold py-3 rounded-xl shadow-lg shadow-indigo-200 hover:-translate-y-0.5 transition-all">
              {loading ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                       : <>Sign in <ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-6">
            Don't have an account?{' '}
            <Link to="/register" className="text-indigo-600 hover:text-indigo-700 font-semibold">Sign up free</Link>
          </p>
          <p className="text-center text-[11px] text-slate-400 mt-5">
            Demo: <code className="bg-slate-100 px-1.5 py-0.5 rounded">admin@ifpi.org / admin123</code><br />
            or <code className="bg-slate-100 px-1.5 py-0.5 rounded">learner@ifpi.org / learner123</code>
          </p>
        </div>
      </div>
    </div>
  )
}

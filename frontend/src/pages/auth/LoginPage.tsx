import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from 'contexts/AuthContext'
import { api } from 'lib/api'
import { GraduationCap, Eye, EyeOff, ArrowRight, BookOpen, Award, Users, Building2 } from 'lucide-react'
import { toast } from 'sonner'

export default function LoginPage() {
  const nav = useNavigate()
  const { login, ssoExchange } = useAuth()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [ssoEnabled, setSsoEnabled] = useState(false)
  const [ssoInitiateUrl, setSsoInitiateUrl] = useState<string | null>(null)
  const [ssoExchanging, setSsoExchanging] = useState(false)
  const [brand, setBrand] = useState<{ name: string; logo_url: string | null; primary_color: string; accent_color: string }>({
    name: 'IFPI Learning', logo_url: null, primary_color: '#262262', accent_color: '#F5A500',
  })

  // Load the org branding for this deployment (public — no auth needed)
  useEffect(() => {
    api.get('/branding/public', { validateStatus: (s) => s < 500 })
      .then(r => { if (r.status === 200 && r.data) setBrand({
        name: r.data.name || 'IFPI Learning',
        logo_url: r.data.logo_url || null,
        primary_color: r.data.primary_color || '#262262',
        accent_color: r.data.accent_color || '#F5A500',
      }) })
      .catch(() => { /* silent — fall back to defaults */ })
  }, [])

  const backend = (import.meta as any).env?.VITE_API_URL
    || (typeof process !== 'undefined' && (process as any).env?.REACT_APP_BACKEND_URL)
    || ''
  const resolvedLogo = brand.logo_url
    ? (brand.logo_url.startsWith('http') ? brand.logo_url : `${backend}${brand.logo_url}`)
    : null

  // Probe SSO availability on mount
  useEffect(() => {
    api.get('/auth/sso-status', { validateStatus: (s) => s < 500 })
      .then(r => {
        if (r.status === 200) {
          setSsoEnabled(!!r.data?.enabled)
          setSsoInitiateUrl(r.data?.initiate_url || null)
        }
      })
      .catch(() => { /* silent */ })
  }, [])

  // If we arrived back from ERP360 with ?erp_token=…, complete the exchange
  useEffect(() => {
    const erpToken = params.get('erp_token')
    if (!erpToken) return
    setSsoExchanging(true)
    ssoExchange(erpToken)
      .then(u => {
        toast.success(`Signed in via ERP360 — welcome, ${u.name || u.email}`)
        nav(u.roles.includes('ADMIN') || u.roles.includes('SUPER_ADMIN') ? '/dashboard' : '/courses')
      })
      .catch(err => {
        setError(err?.response?.data?.detail || 'SSO exchange failed — please try logging in directly')
        setSsoExchanging(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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

  const onSsoClick = () => {
    if (ssoInitiateUrl) {
      // Full redirect — ERP360 will bounce back with ?erp_token=…
      window.location.href = ssoInitiateUrl
    } else {
      toast.error('ERP360 URL not configured — set ERP360_BASE_URL on the backend')
    }
  }

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden flex-col justify-between p-12"
           style={{ backgroundColor: brand.primary_color }}
           data-testid="login-brand-hero">
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full blur-3xl opacity-30"
             style={{ backgroundColor: brand.accent_color }} />
        <div className="absolute bottom-0 right-0 w-80 h-80 rounded-full blur-3xl opacity-20"
             style={{ backgroundColor: brand.accent_color }} />
        <Link to="/" className="relative z-10 flex items-center gap-3" data-testid="login-brand-link">
          {resolvedLogo ? (
            <div className="w-14 h-14 rounded-xl bg-white/95 flex items-center justify-center overflow-hidden shadow-2xl">
              <img src={resolvedLogo} alt={brand.name} className="max-w-[85%] max-h-[85%] object-contain" data-testid="login-brand-logo" />
            </div>
          ) : (
            <div className="w-14 h-14 rounded-xl bg-white/10 flex items-center justify-center shadow-lg">
              <GraduationCap className="h-7 w-7 text-white" />
            </div>
          )}
          <span className="text-white font-bold text-xl tracking-tight">{brand.name}</span>
        </Link>
        <div className="relative z-10 space-y-4">
          {[
            { icon: BookOpen, label: 'Unlimited courses & exams', sub: 'Build and publish in minutes' },
            { icon: Users,    label: 'Manage all your learners',  sub: 'Track progress in real time' },
            { icon: Award,    label: 'Auto-issue certificates',   sub: 'Custom templates & verify codes' },
          ].map(f => (
            <div key={f.label} className="flex items-center gap-4 rounded-2xl p-4 backdrop-blur-sm"
                 style={{ backgroundColor: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.1)' }}>
              <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                   style={{ backgroundColor: `${brand.accent_color}30` }}>
                <f.icon className="h-5 w-5" style={{ color: brand.accent_color }} />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">{f.label}</p>
                <p className="text-xs text-white/60 mt-0.5">{f.sub}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="relative z-10 text-white/70 text-sm italic">&ldquo;The platform that powers {brand.name}&rsquo;s global training network.&rdquo;</p>
      </div>

      <div className="flex-1 flex items-center justify-center p-8 bg-slate-50">
        <div className="w-full max-w-sm">
          <div className="flex lg:hidden items-center gap-2 mb-8 justify-center" data-testid="login-brand-mobile">
            {resolvedLogo ? (
              <div className="w-11 h-11 rounded-xl bg-white flex items-center justify-center overflow-hidden shadow-md border border-slate-200">
                <img src={resolvedLogo} alt={brand.name} className="max-w-[85%] max-h-[85%] object-contain" />
              </div>
            ) : (
              <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ backgroundColor: brand.primary_color }}>
                <GraduationCap className="h-5 w-5 text-white" />
              </div>
            )}
            <span className="text-xl font-bold text-slate-900">{brand.name}</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight font-display">Welcome back</h1>
          <p className="text-slate-500 text-sm mt-1 mb-8">Sign in to continue to your dashboard</p>

          {error && (
            <div className="mb-5 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm" data-testid="login-error">
              {error}
            </div>
          )}

          {ssoExchanging && (
            <div data-testid="sso-exchanging" className="mb-5 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-xl px-4 py-3 text-sm flex items-center gap-2">
              <span className="w-3 h-3 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
              Completing ERP360 sign-in…
            </div>
          )}

          {ssoEnabled && !ssoExchanging && (
            <>
              <button type="button" onClick={onSsoClick} data-testid="sso-login-button"
                className="w-full mb-4 flex items-center justify-center gap-2 bg-white border border-slate-300 hover:border-indigo-400 hover:bg-indigo-50/40 text-slate-800 font-semibold py-3 rounded-xl transition-all">
                <Building2 className="h-4 w-4 text-indigo-600" />
                Continue with ERP360
              </button>
              <div className="flex items-center gap-3 mb-4">
                <div className="flex-1 h-px bg-slate-200" />
                <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">or sign in directly</span>
                <div className="flex-1 h-px bg-slate-200" />
              </div>
            </>
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
              style={{ backgroundColor: brand.primary_color }}
              className="w-full flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-60 text-white font-semibold py-3 rounded-xl shadow-lg hover:-translate-y-0.5 transition-all">
              {loading ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                       : <>Sign in <ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-6">
            Don&apos;t have an account?{' '}
            <Link to="/register" style={{ color: brand.primary_color }}
                  className="hover:opacity-80 font-semibold">Sign up free</Link>
          </p>
          <div className="text-center mt-3">
            <Link to="/public" data-testid="login-browse-courses"
              className="text-xs text-slate-500 hover:text-slate-700 inline-flex items-center gap-1.5">
              <span>📚</span> Browse the public catalog · verify a certificate
            </Link>
          </div>
          <p className="text-center text-[11px] text-slate-400 mt-5">
            Demo: <code className="bg-slate-100 px-1.5 py-0.5 rounded">admin@ifpi.org / admin123</code><br />
            or <code className="bg-slate-100 px-1.5 py-0.5 rounded">learner@ifpi.org / learner123</code>
          </p>
        </div>
      </div>
    </div>
  )
}

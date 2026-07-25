import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from 'contexts/AuthContext'
import { api } from 'lib/api'
import { GraduationCap } from 'lucide-react'
import { toast } from 'sonner'

export default function RegisterPage() {
  const nav = useNavigate()
  const { register } = useAuth()
  const [name, setName] = useState(''); const [email, setEmail] = useState('')
  const [password, setPassword] = useState(''); const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [brand, setBrand] = useState<{ name: string; logo_url: string | null; primary_color: string; accent_color: string }>({
    name: 'IFPI Learning', logo_url: null, primary_color: '#262262', accent_color: '#F5A500',
  })

  useEffect(() => {
    api.get('/branding/public', { validateStatus: (s) => s < 500 })
      .then(r => { if (r.status === 200 && r.data) setBrand({
        name: r.data.name || 'IFPI Learning',
        logo_url: r.data.logo_url || null,
        primary_color: r.data.primary_color || '#262262',
        accent_color: r.data.accent_color || '#F5A500',
      }) })
      .catch(() => {})
  }, [])

  const backend = process.env.REACT_APP_BACKEND_URL || ''
  const resolvedLogo = brand.logo_url
    ? (brand.logo_url.startsWith('http') ? brand.logo_url : `${backend}${brand.logo_url}`)
    : null

  const onSubmit = async (e: React.FormEvent) => {
  const resolvedLogo = brand.logo_url
    ? (brand.logo_url.startsWith('http') ? brand.logo_url : `${backend}${brand.logo_url}`)
    : null

  const onSubmit = async (e: React.FormEvent) => {
  const resolvedLogo = brand.logo_url
    ? (brand.logo_url.startsWith('http') ? brand.logo_url : `${backend}${brand.logo_url}`)
    : null
  const resolvedLogo = brand.logo_url
    || (typeof process !== 'undefined' && (process as any).env?.REACT_APP_BACKEND_URL) || ''
  const resolvedLogo = brand.logo_url
    ? (brand.logo_url.startsWith('http') ? brand.logo_url : `${backend}${brand.logo_url}`)
    : null

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setLoading(true); setError('')
    try {
      await register(email, password, name)
      toast.success('Welcome to IFPI Learning!')
      nav('/courses')
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Registration failed')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4"
         style={{ background: `linear-gradient(135deg, ${brand.primary_color}12 0%, #ffffff 55%, ${brand.accent_color}18 100%)` }}
         data-testid="register-page">
      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center gap-3 justify-center mb-8" data-testid="register-brand-link">
          {resolvedLogo ? (
            <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center overflow-hidden shadow-md border border-slate-200">
              <img src={resolvedLogo} alt={brand.name} className="max-w-[85%] max-h-[85%] object-contain" data-testid="register-brand-logo" />
            </div>
          ) : (
            <div className="w-10 h-10 rounded-xl flex items-center justify-center shadow-lg" style={{ backgroundColor: brand.primary_color }}>
              <GraduationCap className="h-5 w-5 text-white" />
            </div>
          )}
          <span className="text-2xl font-bold text-slate-900 font-display">{brand.name}</span>
        </Link>
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <h1 className="text-2xl font-bold text-slate-900 text-center font-display">Create your account</h1>
          <p className="text-slate-500 text-sm text-center mt-1 mb-6">Start your free trial — no credit card needed</p>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm" data-testid="register-error">
              {error}
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4" data-testid="register-form">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Full name</label>
              <input type="text" required value={name} onChange={e => setName(e.target.value)} data-testid="register-name"
                className="w-full px-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2" style={{ boxShadow: `0 0 0 0 ${brand.primary_color}00` }} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)} data-testid="register-email"
                className="w-full px-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
              <input type="password" required minLength={8} value={password} onChange={e => setPassword(e.target.value)} data-testid="register-password"
                placeholder="Min. 8 characters"
                className="w-full px-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2" />
            </div>
            <button type="submit" disabled={loading} data-testid="register-submit"
              style={{ backgroundColor: brand.primary_color }}
              className="w-full hover:opacity-90 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg transition-all">
              {loading ? 'Creating account…' : 'Get started free'}
            </button>
            <p className="text-xs text-slate-500 text-center">
              All new accounts are created as Learners. Admins are invited by your academy.
            </p>
          </form>
          <p className="text-center text-sm text-slate-600 mt-4">
            Already have an account? <Link to="/login" style={{ color: brand.primary_color }} className="hover:opacity-80 font-medium">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}

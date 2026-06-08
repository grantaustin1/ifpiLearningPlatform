import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from 'lib/api'
import { GraduationCap, BookOpen, Users, Clock, ArrowRight } from 'lucide-react'
import { formatCurrency } from 'lib/utils'

export default function PortalPage() {
  const { slug } = useParams()
  const nav = useNavigate()
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get(`/portal/${slug}`).then(r => setData(r.data)).catch(e => setError(e?.response?.data?.detail || 'Academy not found'))
  }, [slug])

  if (error) return (
    <div className="min-h-screen flex items-center justify-center"><div className="text-center"><h1 className="text-2xl font-bold">{error}</h1><Link to="/" className="text-indigo-600 hover:underline mt-3 inline-block">← Go home</Link></div></div>
  )
  if (!data) return <div className="min-h-screen flex items-center justify-center"><div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>

  const accent = data.organization.primary_color || '#6366f1'
  return (
    <div className="min-h-screen bg-white" data-testid="portal-page">
      <nav className="border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-5 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {data.organization.logo_url ? <img src={data.organization.logo_url} className="h-8" alt="" /> : (
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: accent }}><GraduationCap className="h-4 w-4 text-white" /></div>
            )}
            <span className="font-bold text-slate-900">{data.organization.name}</span>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/login" className="text-sm font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5">Sign in</Link>
            <Link to="/register" className="text-sm font-semibold text-white px-4 py-2 rounded-lg" style={{ background: accent }}>Get started</Link>
          </div>
        </div>
      </nav>

      <header className="py-20 px-5 text-center" style={{ background: `linear-gradient(180deg, ${accent}15, transparent)` }}>
        <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 tracking-tight font-display">{data.organization.name}</h1>
        {data.organization.description && <p className="text-lg text-slate-500 mt-4 max-w-2xl mx-auto">{data.organization.description}</p>}
        <div className="flex justify-center gap-6 mt-8 text-sm text-slate-500">
          <span className="flex items-center gap-1.5"><BookOpen className="h-4 w-4" /> {data.stats.courses} courses</span>
          <span className="flex items-center gap-1.5"><Users className="h-4 w-4" /> {data.stats.learners} learners</span>
        </div>
      </header>

      <section className="max-w-6xl mx-auto px-5 py-12">
        <h2 className="text-2xl font-bold text-slate-900 mb-6 font-display">Courses</h2>
        {data.courses.length === 0 ? <p className="text-slate-400">No courses published yet.</p> : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.courses.map((c: any) => (
              <div key={c.id} className="bg-white rounded-2xl border border-slate-200 hover:shadow-md transition-shadow" data-testid={`portal-course-${c.id}`}>
                <div className={`h-28 rounded-t-2xl ${c.cover_color}`} />
                <div className="p-5">
                  <h3 className="font-semibold">{c.title}</h3>
                  {c.description && <p className="text-xs text-slate-500 mt-1 line-clamp-2">{c.description}</p>}
                  <div className="flex items-center justify-between mt-3">
                    <span className="text-xs text-slate-400 flex items-center gap-1"><Clock className="h-3 w-3" /> {c.duration_minutes || 0}m</span>
                    <span className="text-sm font-semibold">{c.price_cents === 0 ? 'Free' : formatCurrency(c.price_cents, c.currency)}</span>
                  </div>
                  <button onClick={() => nav('/register')} className="w-full mt-4 inline-flex items-center justify-center gap-1.5 text-xs text-white py-2 rounded-lg font-medium" style={{ background: accent }}>
                    Enrol <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

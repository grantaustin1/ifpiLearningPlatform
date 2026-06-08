import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from 'contexts/AuthContext'
import { api } from 'lib/api'
import { BookOpen, Search, GraduationCap, Clock, Users } from 'lucide-react'
import { formatCurrency } from 'lib/utils'

export default function CatalogPage() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')

  const { data, isLoading } = useQuery<any>({
    queryKey: ['catalog', search, category],
    queryFn: async () => (await api.get('/catalog', { params: { q: search || undefined, category: category || undefined } })).data,
  })

  const handleEnroll = async (c: any) => {
    if (!user) { nav('/login'); return }
    if (c.price_cents > 0) {
      const r = await api.post('/billing/subscribe', { course_id: c.id })
      if (r.data.is_stub) { /* falls through to enrol below */ }
    }
    await api.post(`/courses/${c.id}/enroll`)
    nav(`/learn/${c.id}`)
  }

  return (
    <div className="min-h-screen bg-white">
      <nav className="border-b border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <GraduationCap className="text-white h-4 w-4" />
            </div>
            <span className="font-bold text-slate-900 text-[15px]">IFPI Learning</span>
          </Link>
          <div className="flex items-center gap-2.5">
            {user ? (
              <Link to="/courses" className="text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg">My dashboard</Link>
            ) : (
              <>
                <Link to="/login" className="text-sm font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5">Sign in</Link>
                <Link to="/register" className="text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg">Get started</Link>
              </>
            )}
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-5 py-12" data-testid="catalog-page">
        <h1 className="text-3xl font-bold text-slate-900 font-display">Course catalog</h1>
        <p className="text-slate-500 mt-1">Browse all published courses</p>

        <div className="flex gap-3 mt-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search courses…" data-testid="catalog-search"
              className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
          <select value={category} onChange={e => setCategory(e.target.value)} className="border border-slate-200 rounded-lg px-3 py-2 text-sm">
            <option value="">All categories</option>
            {(data?.categories || []).map((c: string) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        {isLoading ? <div className="flex items-center justify-center py-16"><div className="w-7 h-7 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div> :
         (data?.courses || []).length === 0 ? (
          <div className="text-center py-16 text-slate-400">
            <BookOpen className="h-12 w-12 text-slate-300 mx-auto mb-4" /> No courses match.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-8">
            {data.courses.map((c: any) => (
              <div key={c.id} className="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-shadow border border-slate-100" data-testid={`catalog-card-${c.id}`}>
                <div className={`h-32 ${c.cover_color} p-4 flex items-end`}>
                  {c.category && <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-white/20 text-white">{c.category}</span>}
                </div>
                <div className="p-5">
                  <h3 className="font-semibold text-slate-900">{c.title}</h3>
                  {c.description && <p className="text-xs text-slate-500 mt-1.5 line-clamp-2">{c.description}</p>}
                  <div className="flex items-center gap-3 mt-3 text-xs text-slate-500">
                    <span className="flex items-center gap-1"><BookOpen className="h-3.5 w-3.5" /> {c.slide_count} slides</span>
                    {c.duration_minutes && <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {c.duration_minutes}m</span>}
                    <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {c.enrollment_count}</span>
                  </div>
                  <div className="flex items-center justify-between mt-4">
                    <p className="text-sm font-semibold">{c.price_cents === 0 ? 'Free' : formatCurrency(c.price_cents, c.currency)}</p>
                    <button onClick={() => handleEnroll(c)} data-testid={`enroll-btn-${c.id}`}
                      className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-lg font-medium">
                      {c.price_cents === 0 ? 'Enrol' : 'Subscribe'}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

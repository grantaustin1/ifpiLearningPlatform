import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from 'contexts/AuthContext'
import { api } from 'lib/api'
import { BookOpen, Search, GraduationCap, Clock, Users, Sparkles, ArrowRight, TrendingUp, Star } from 'lucide-react'
import { formatCurrency } from 'lib/utils'
import { ShareCourseButton } from 'components/ShareCourseButton'

interface CatalogCourse {
  id: number
  title: string
  description?: string | null
  category?: string | null
  cover_color: string
  cover_image?: string | null
  is_featured?: boolean
  avg_rating?: number | null
  rating_count?: number
  duration_minutes?: number | null
  price_cents: number
  currency: string
  slide_count: number
  enrollment_count: number
  organization?: { id: number; name: string; logo_url?: string | null } | null
}

interface CatalogResponse {
  courses: CatalogCourse[]
  categories: string[]
  total?: number
  page?: number
  page_size?: number
}

function CourseCard({ c, onEnroll }: { c: CatalogCourse; onEnroll: (c: CatalogCourse) => void }) {
  return (
    <div className="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-shadow border border-slate-100 flex flex-col" data-testid={`catalog-card-${c.id}`}>
      <Link to={`/catalog/${c.id}`} className="block group">
        <div className={`aspect-video sm:aspect-auto sm:h-32 ${c.cover_color} p-4 flex items-end relative overflow-hidden`}>
          {c.cover_image && (
            <>
              <img src={c.cover_image} alt={c.title} loading="lazy"
                className="absolute inset-0 w-full h-full object-cover pointer-events-none group-hover:scale-105 transition-transform duration-500"
                data-testid={`catalog-cover-img-${c.id}`} />
              <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent pointer-events-none" />
            </>
          )}
          {c.category && <span className="relative z-10 text-[10px] font-medium px-2 py-0.5 rounded-full bg-white/20 backdrop-blur-sm text-white">{c.category}</span>}
        </div>
      </Link>
      <div className="p-5 flex-1 flex flex-col">
        <Link to={`/catalog/${c.id}`} className="group">
          <h3 className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors" data-testid={`catalog-title-${c.id}`}>{c.title}</h3>
        </Link>
        {c.organization && (
          <p className="text-[11px] text-slate-400 mt-0.5">by {c.organization.name}</p>
        )}
        {c.description && <p className="text-xs text-slate-500 mt-1.5 line-clamp-2">{c.description}</p>}
        <div className="flex items-center gap-3 mt-3 text-xs text-slate-500">
          <span className="flex items-center gap-1"><BookOpen className="h-3.5 w-3.5" /> {c.slide_count} slides</span>
          {c.duration_minutes && <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {c.duration_minutes}m</span>}
          {c.avg_rating != null && (c.rating_count || 0) > 0 && (
            <span className="flex items-center gap-1 text-amber-500 font-semibold" data-testid={`catalog-rating-${c.id}`}>
              <Star className="h-3.5 w-3.5 fill-current" /> {c.avg_rating}
              <span className="text-slate-400 font-normal">({c.rating_count})</span>
            </span>
          )}
          <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {c.enrollment_count}</span>
        </div>
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-50">
          <p className="text-sm font-semibold text-slate-900">{c.price_cents === 0 ? 'Free' : formatCurrency(c.price_cents, c.currency)}</p>
          <div className="flex items-center gap-1.5">
            <ShareCourseButton courseId={c.id} />
            <button onClick={() => onEnroll(c)} data-testid={`enroll-btn-${c.id}`}
              className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-lg font-medium transition-colors">
              {c.price_cents === 0 ? 'Enrol' : 'Get access'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function CatalogPage() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [org, setOrg] = useState<number | ''>('')
  const [sort, setSort] = useState<'newest' | 'price_asc' | 'price_desc' | 'most_enrolled'>('newest')

  const { data, isLoading } = useQuery<CatalogResponse>({
    queryKey: ['catalog', search, category, org, sort],
    queryFn: async () => (await api.get('/catalog', {
      params: {
        q: search || undefined,
        category: category || undefined,
        org: org || undefined,
        sort, page_size: 24,
      },
    })).data,
  })

  // Iter 27 — Cross-tenant marketplace: list opted-in orgs for filter
  const { data: orgs } = useQuery<Array<{
    id: number; name: string; logo_url: string | null; course_count: number
  }>>({
    queryKey: ['catalog-organizations'],
    queryFn: async () => (await api.get('/catalog/organizations')).data,
    staleTime: 5 * 60_000,
  })

  const { data: featured } = useQuery<CatalogResponse>({
    queryKey: ['catalog-featured'],
    queryFn: async () => (await api.get('/catalog', { params: { featured: true } })).data,
    // Featured stays consistent even when the user types a search
    staleTime: 60_000,
  })

  const handleEnroll = async (c: CatalogCourse) => {
    if (!user) { nav(`/register?next=/catalog/${c.id}&auto_enroll=1`); return }
    try {
      if (c.price_cents > 0) {
        await api.post('/billing/subscribe', { course_id: c.id })
      }
      await api.post(`/courses/${c.id}/enroll`)
      nav(`/learn/${c.id}`)
    } catch {
      // Fallback to detail page on any failure so user still has a path forward
      nav(`/catalog/${c.id}`)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="border-b border-slate-200 bg-white sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <GraduationCap className="text-white h-4 w-4" />
            </div>
            <span className="font-bold text-slate-900 text-[15px]">IFPI Learning</span>
          </Link>
          <div className="flex items-center gap-2.5">
            {user ? (
              <Link to="/courses" className="text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg" data-testid="nav-dashboard">My dashboard</Link>
            ) : (
              <>
                <Link to="/login" className="text-sm font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5" data-testid="nav-login">Sign in</Link>
                <Link to="/register" className="text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg" data-testid="nav-register">Get started</Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="bg-gradient-to-br from-indigo-600 via-violet-600 to-indigo-700 text-white">
        <div className="max-w-6xl mx-auto px-5 py-16 sm:py-20" data-testid="marketplace-hero">
          <div className="inline-flex items-center gap-2 bg-white/15 backdrop-blur-sm px-3 py-1.5 rounded-full text-xs font-medium mb-5">
            <Sparkles className="h-3.5 w-3.5" /> Marketplace
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight mb-4 font-display">
            Learn from the world&apos;s leading fitness academies.
          </h1>
          <p className="text-lg text-indigo-100 max-w-2xl mb-8">
            Browse published courses from IFPI-accredited academies, gyms and wellness studios. Enrol in minutes — free or paid, your choice.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 max-w-2xl">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search courses, categories, academies…"
                data-testid="catalog-search"
                className="w-full pl-11 pr-4 py-3 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-4 focus:ring-white/30"
              />
            </div>
            {!user && (
              <Link to="/register" data-testid="hero-get-started-btn"
                className="inline-flex items-center justify-center gap-2 bg-white text-indigo-700 font-semibold px-6 py-3 rounded-xl shadow-lg hover:-translate-y-0.5 transition-all whitespace-nowrap">
                Get started free <ArrowRight className="h-4 w-4" />
              </Link>
            )}
          </div>
        </div>
      </section>

      <div className="max-w-6xl mx-auto px-5 py-12" data-testid="catalog-page">
        {/* Featured */}
        {featured?.courses && featured.courses.length > 0 && !search && !category && (
          <div className="mb-14" data-testid="featured-section">
            <div className="flex items-center gap-2 mb-5">
              <TrendingUp className="h-4 w-4 text-indigo-600" />
              <h2 className="text-sm font-semibold uppercase tracking-widest text-indigo-600">Featured</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {featured.courses.slice(0, 3).map(c => <CourseCard key={c.id} c={c} onEnroll={handleEnroll} />)}
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-6">
          <h2 className="text-lg font-semibold text-slate-900 flex-1">
            {search || category ? 'Results' : 'All courses'}
            {typeof data?.total === 'number' && (
              <span className="text-sm font-normal text-slate-400 ml-2">({data.total})</span>
            )}
          </h2>
          <select value={category} onChange={e => setCategory(e.target.value)} data-testid="catalog-category-filter"
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white">
            <option value="">All categories</option>
            {(data?.categories || []).map((c: string) => <option key={c} value={c}>{c}</option>)}
          </select>
          {orgs && orgs.length > 1 && (
            <select value={org} onChange={e => setOrg(e.target.value === '' ? '' : parseInt(e.target.value))}
              data-testid="catalog-org-filter"
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white">
              <option value="">All publishers</option>
              {orgs.map(o => (
                <option key={o.id} value={o.id}>{o.name} ({o.course_count})</option>
              ))}
            </select>
          )}
          <select value={sort} onChange={e => setSort(e.target.value as typeof sort)} data-testid="catalog-sort"
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white">
            <option value="newest">Newest</option>
            <option value="most_enrolled">Most enrolled</option>
            <option value="price_asc">Price: low to high</option>
            <option value="price_desc">Price: high to low</option>
          </select>
        </div>

        {isLoading ? <div className="flex items-center justify-center py-16"><div className="w-7 h-7 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div> :
         (data?.courses || []).length === 0 ? (
          <div className="text-center py-16 text-slate-400" data-testid="catalog-empty">
            <BookOpen className="h-12 w-12 text-slate-300 mx-auto mb-4" /> No courses match your search.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="catalog-grid">
            {data.courses.map(c => <CourseCard key={c.id} c={c} onEnroll={handleEnroll} />)}
          </div>
        )}
      </div>
    </div>
  )
}

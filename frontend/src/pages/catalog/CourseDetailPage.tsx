import { useEffect } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from 'contexts/AuthContext'
import { api } from 'lib/api'
import {
  ArrowLeft, ArrowRight, BookOpen, CheckCircle, Clock, GraduationCap, Users, Building2,
} from 'lucide-react'
import { formatCurrency } from 'lib/utils'

interface CourseDetail {
  id: number
  title: string
  description?: string | null
  category?: string | null
  cover_color: string
  duration_minutes?: number | null
  price_cents: number
  currency: string
  slide_count: number
  enrollment_count: number
  syllabus_preview: { title: string; order_index: number }[]
  organization?: { id: number; name: string; logo_url?: string | null } | null
}

export default function CourseDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const autoEnroll = params.get('auto_enroll') === '1'

  const { data, isLoading, error } = useQuery<CourseDetail>({
    queryKey: ['catalog-detail', id],
    queryFn: async () => (await api.get(`/catalog/${id}`)).data,
    enabled: !!id,
  })

  // Iter 24 — Marketplace funnel: fire a view impression once per
  // detail-page mount. Backend dedups by (user_or_anon, course, day),
  // so refresh spamming doesn't inflate the funnel.
  useEffect(() => {
    if (!id) return
    api.post(`/catalog/${id}/track-view`, {
      referrer: document.referrer || null,
    }).catch(() => { /* fire-and-forget — never break UX */ })
  }, [id])

  const handleEnroll = async () => {
    if (!data) return
    if (!user) {
      nav(`/register?next=/catalog/${data.id}&auto_enroll=1`)
      return
    }
    try {
      if (data.price_cents > 0) {
        // Iter 39: Stripe checkout for paid courses. Backend returns a
        // hosted checkout URL; we redirect the browser to it. On
        // return the /billing/success page polls status and enrolls.
        const r = await api.post('/payments/v1/checkout/session', {
          course_id: data.id,
          origin_url: window.location.origin,
        })
        if (r.data?.url) {
          window.location.href = r.data.url
          return
        }
        throw new Error('Checkout URL missing from response')
      }
      await api.post(`/courses/${data.id}/enroll`)
      nav(`/learn/${data.id}`)
    } catch (e) {
      console.error('Enroll failed', e)
    }
  }

  // Auto-enroll after signup handoff
  useEffect(() => {
    if (autoEnroll && user && data) {
      handleEnroll()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoEnroll, user, data?.id])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-slate-500" data-testid="course-not-found">
        <BookOpen className="h-10 w-10 text-slate-300" />
        <p>Course not found or not publicly listed.</p>
        <Link to="/catalog" className="text-indigo-600 text-sm font-medium">← Back to marketplace</Link>
      </div>
    )
  }

  const isFree = data.price_cents === 0

  return (
    <div className="min-h-screen bg-white">
      <nav className="border-b border-slate-200 bg-white">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
          <Link to="/catalog" className="flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900" data-testid="back-to-catalog">
            <ArrowLeft className="h-4 w-4" /> Marketplace
          </Link>
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <GraduationCap className="text-white h-4 w-4" />
            </div>
            <span className="font-bold text-slate-900 text-[15px]">IFPI Learning</span>
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <div className={`${data.cover_color} text-white`}>
        <div className="max-w-6xl mx-auto px-5 sm:px-8 py-12 sm:py-16" data-testid="course-detail-hero">
          {data.category && (
            <span className="inline-block text-[10px] font-semibold uppercase tracking-widest bg-white/20 backdrop-blur-sm px-2.5 py-1 rounded-full mb-4">
              {data.category}
            </span>
          )}
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight mb-4 font-display" data-testid="course-title">
            {data.title}
          </h1>
          {data.description && (
            <p className="text-lg text-white/90 max-w-2xl leading-relaxed">{data.description}</p>
          )}
          <div className="flex flex-wrap items-center gap-5 mt-6 text-sm text-white/80">
            {data.organization && (
              <span className="flex items-center gap-1.5"><Building2 className="h-4 w-4" /> {data.organization.name}</span>
            )}
            <span className="flex items-center gap-1.5"><BookOpen className="h-4 w-4" /> {data.slide_count} lessons</span>
            {data.duration_minutes && (
              <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" /> {data.duration_minutes} min</span>
            )}
            <span className="flex items-center gap-1.5"><Users className="h-4 w-4" /> {data.enrollment_count} enrolled</span>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="max-w-6xl mx-auto px-5 sm:px-8 py-12 grid grid-cols-1 lg:grid-cols-3 gap-10">
        {/* Left: syllabus */}
        <div className="lg:col-span-2">
          <h2 className="text-xl font-bold text-slate-900 mb-5">What you&apos;ll learn</h2>
          {data.syllabus_preview.length === 0 ? (
            <p className="text-slate-400 text-sm">Syllabus is being finalised.</p>
          ) : (
            <ul className="space-y-3" data-testid="syllabus-preview">
              {data.syllabus_preview.map(s => (
                <li key={s.order_index} className="flex items-start gap-3 p-3 rounded-lg border border-slate-100 hover:border-slate-200 transition-colors">
                  <div className="w-7 h-7 rounded-full bg-indigo-50 text-indigo-600 text-xs font-bold flex items-center justify-center flex-shrink-0">
                    {s.order_index + 1}
                  </div>
                  <div className="pt-0.5">
                    <p className="text-sm font-medium text-slate-800">{s.title}</p>
                  </div>
                </li>
              ))}
              {data.slide_count > data.syllabus_preview.length && (
                <li className="text-sm text-slate-400 pl-10 pt-2">
                  + {data.slide_count - data.syllabus_preview.length} more lessons after you enrol
                </li>
              )}
            </ul>
          )}
        </div>

        {/* Right: CTA card */}
        <aside className="lg:sticky lg:top-24 self-start">
          <div className="rounded-2xl border border-slate-200 shadow-sm p-6 bg-white">
            <p className="text-3xl font-extrabold text-slate-900 mb-1" data-testid="course-price">
              {isFree ? 'Free' : formatCurrency(data.price_cents, data.currency)}
            </p>
            <p className="text-xs text-slate-400 mb-5">{isFree ? 'Enrol instantly, no payment' : 'One-time access via ERP360 billing'}</p>
            <button onClick={handleEnroll} data-testid="cta-enroll"
              className="w-full inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-4 py-3 rounded-xl shadow-sm transition-colors">
              {user ? (isFree ? 'Enrol now' : 'Get access') : 'Get started'} <ArrowRight className="h-4 w-4" />
            </button>
            <ul className="mt-5 space-y-2.5 text-sm text-slate-600">
              <li className="flex items-center gap-2"><CheckCircle className="h-4 w-4 text-emerald-500" /> Lifetime access</li>
              <li className="flex items-center gap-2"><CheckCircle className="h-4 w-4 text-emerald-500" /> Certificate on completion</li>
              <li className="flex items-center gap-2"><CheckCircle className="h-4 w-4 text-emerald-500" /> Learn at your own pace</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  )
}

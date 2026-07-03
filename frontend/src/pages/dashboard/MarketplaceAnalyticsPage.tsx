import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { BarChart3, Eye, GraduationCap, Trophy, TrendingUp, TrendingDown, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'

interface Rollup {
  days_window: number
  totals: { views: number; enrollments: number; completions: number; courses_with_activity: number }
  view_to_enroll_rate: number
  enroll_to_complete_rate: number
  top_by_conversion: {
    course_id: number
    course_title: string
    views: number
    enrollments: number
    completions: number
    view_to_enroll_rate: number
    enroll_to_complete_rate: number
  }[]
  daily: { date: string; views: number; enrollments: number; completions: number }[]
}

export default function MarketplaceAnalyticsPage() {
  const [data, setData] = useState<Rollup | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    setLoading(true)
    api.get('/admin/marketplace-funnel', { params: { days, top_n: 10 } })
      .then(r => setData(r.data))
      .finally(() => setLoading(false))
  }, [days])

  const fmtPct = (v: number) => `${(v * 100).toFixed(1)}%`

  if (loading || !data) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[50vh]">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
      </div>
    )
  }

  const maxDaily = Math.max(1, ...data.daily.map(d => Math.max(d.views, d.enrollments, d.completions)))

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6" data-testid="marketplace-analytics-page">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-indigo-600" /> Marketplace analytics
          </h1>
          <p className="text-sm text-slate-500 mt-1">Cross-course funnel roll-up across your entire academy.</p>
        </div>
        <select value={days} onChange={e => setDays(parseInt(e.target.value))}
          data-testid="rollup-days-select"
          className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white">
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
          <option value={365}>Last year</option>
        </select>
      </div>

      {/* Top totals */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3" data-testid="rollup-totals">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <Eye className="h-5 w-5 text-slate-500 mb-2" />
          <p className="text-3xl font-bold text-slate-900">{data.totals.views}</p>
          <p className="text-xs text-slate-500 uppercase tracking-wide mt-1">Views</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <GraduationCap className="h-5 w-5 text-indigo-600 mb-2" />
          <p className="text-3xl font-bold text-slate-900">{data.totals.enrollments}</p>
          <p className="text-xs text-slate-500 uppercase tracking-wide mt-1">Enrolments</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <Trophy className="h-5 w-5 text-emerald-500 mb-2" />
          <p className="text-3xl font-bold text-slate-900">{data.totals.completions}</p>
          <p className="text-xs text-slate-500 uppercase tracking-wide mt-1">Completions</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <BarChart3 className="h-5 w-5 text-amber-500 mb-2" />
          <p className="text-3xl font-bold text-slate-900">{data.totals.courses_with_activity}</p>
          <p className="text-xs text-slate-500 uppercase tracking-wide mt-1">Active courses</p>
        </div>
      </div>

      {/* Rates */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-900 mb-4">Conversion rates</h2>
        <div className="space-y-3">
          <div className="flex items-center justify-between" data-testid="rollup-v-to-e">
            <span className="text-sm text-slate-600">View → Enrol</span>
            <span className={`font-bold text-lg flex items-center gap-1 ${data.view_to_enroll_rate >= 0.1 ? 'text-emerald-600' : 'text-slate-500'}`}>
              {data.view_to_enroll_rate >= 0.1 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
              {fmtPct(data.view_to_enroll_rate)}
            </span>
          </div>
          <div className="flex items-center justify-between" data-testid="rollup-e-to-c">
            <span className="text-sm text-slate-600">Enrol → Complete</span>
            <span className={`font-bold text-lg flex items-center gap-1 ${data.enroll_to_complete_rate >= 0.5 ? 'text-emerald-600' : 'text-slate-500'}`}>
              {data.enroll_to_complete_rate >= 0.5 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
              {fmtPct(data.enroll_to_complete_rate)}
            </span>
          </div>
        </div>
      </div>

      {/* Top by conversion */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-900 mb-4">Top courses by view→enrol conversion</h2>
        {data.top_by_conversion.length === 0 ? (
          <p className="text-sm text-slate-400">No courses with tracked views in this window.</p>
        ) : (
          <div className="divide-y divide-slate-100" data-testid="top-by-conversion">
            {data.top_by_conversion.map(c => (
              <Link key={c.course_id} to={`/courses/${c.course_id}/edit`}
                className="flex items-center justify-between py-3 hover:bg-slate-50 -mx-2 px-2 rounded-lg transition-colors"
                data-testid={`top-course-${c.course_id}`}>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-900 truncate">{c.course_title}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {c.views} views · {c.enrollments} enrols · {c.completions} completes
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-base font-bold text-emerald-600">{fmtPct(c.view_to_enroll_rate)}</p>
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider">V→E</p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Sparkline */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-900 mb-4">Daily trend</h2>
        <div className="flex items-end gap-1 h-24" data-testid="rollup-sparkline">
          {data.daily.slice(-30).map(d => (
            <div key={d.date} className="flex-1 flex flex-col gap-[1px] justify-end"
              title={`${d.date}: ${d.views} views · ${d.enrollments} enrolls · ${d.completions} completes`}>
              <div className="bg-emerald-500 rounded-sm" style={{ height: `${(d.completions / maxDaily) * 100}%` }} />
              <div className="bg-indigo-500 rounded-sm" style={{ height: `${(d.enrollments / maxDaily) * 100}%` }} />
              <div className="bg-slate-300 rounded-sm" style={{ height: `${(d.views / maxDaily) * 100}%` }} />
            </div>
          ))}
        </div>
        <div className="flex items-center gap-4 mt-3 text-[11px] text-slate-500">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-300 inline-block" /> Views</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-indigo-500 inline-block" /> Enrols</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> Completes</span>
        </div>
      </div>
    </div>
  )
}

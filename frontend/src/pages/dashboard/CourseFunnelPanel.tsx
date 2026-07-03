import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { BarChart3, Eye, GraduationCap, Trophy, TrendingUp, TrendingDown, Loader2 } from 'lucide-react'

interface FunnelData {
  course_id: number
  course_title: string
  days_window: number
  views: number
  enrollments: number
  completions: number
  view_to_enroll_rate: number
  enroll_to_complete_rate: number
  daily: { date: string; views: number; enrollments: number; completions: number }[]
}

interface Props {
  courseId: number
}

/**
 * Iter 24 — Marketplace funnel analytics panel.
 * Embedded on the course edit page (right rail). Shows the V→E→C
 * funnel + last-30-day sparklines for a single course.
 */
export function CourseFunnelPanel({ courseId }: Props) {
  const [data, setData] = useState<FunnelData | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    setLoading(true)
    api.get(`/admin/marketplace-funnel/${courseId}`, { params: { days } })
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [courseId, days])

  const fmtPct = (v: number) => `${(v * 100).toFixed(1)}%`

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 p-5 bg-white" data-testid="funnel-panel-loading">
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    )
  }
  if (!data) return null

  const rows = [
    { label: 'Views', value: data.views, icon: Eye, color: 'text-slate-600', bg: 'bg-slate-100' },
    { label: 'Enrolments', value: data.enrollments, icon: GraduationCap, color: 'text-indigo-600', bg: 'bg-indigo-50' },
    { label: 'Completions', value: data.completions, icon: Trophy, color: 'text-emerald-600', bg: 'bg-emerald-50' },
  ]

  const maxDaily = Math.max(1, ...data.daily.map(d => Math.max(d.views, d.enrollments, d.completions)))

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="funnel-panel">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-900 flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-indigo-600" /> Marketplace funnel
        </h3>
        <select value={days} onChange={e => setDays(parseInt(e.target.value))}
          data-testid="funnel-days-select"
          className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white">
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-5" data-testid="funnel-counts">
        {rows.map(r => (
          <div key={r.label} className={`rounded-xl ${r.bg} p-3 flex flex-col gap-1`}>
            <r.icon className={`h-4 w-4 ${r.color}`} />
            <p className="text-2xl font-bold text-slate-900">{r.value}</p>
            <p className="text-[11px] uppercase font-medium tracking-wide text-slate-500">{r.label}</p>
          </div>
        ))}
      </div>

      <div className="space-y-2 mb-5">
        <div className="flex items-center justify-between text-sm" data-testid="funnel-v-to-e">
          <span className="text-slate-600">View → Enrol</span>
          <span className={`font-semibold flex items-center gap-1 ${data.view_to_enroll_rate >= 0.1 ? 'text-emerald-600' : 'text-slate-500'}`}>
            {data.view_to_enroll_rate >= 0.1 ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
            {fmtPct(data.view_to_enroll_rate)}
          </span>
        </div>
        <div className="flex items-center justify-between text-sm" data-testid="funnel-e-to-c">
          <span className="text-slate-600">Enrol → Complete</span>
          <span className={`font-semibold flex items-center gap-1 ${data.enroll_to_complete_rate >= 0.5 ? 'text-emerald-600' : 'text-slate-500'}`}>
            {data.enroll_to_complete_rate >= 0.5 ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
            {fmtPct(data.enroll_to_complete_rate)}
          </span>
        </div>
      </div>

      {/* Sparkline — small CSS bar chart, no external lib */}
      <div>
        <p className="text-[11px] uppercase font-medium tracking-wide text-slate-400 mb-2">Daily trend</p>
        <div className="flex items-end gap-[2px] h-16" data-testid="funnel-sparkline">
          {data.daily.slice(-30).map(d => (
            <div key={d.date} className="flex-1 flex flex-col gap-[1px] justify-end" title={`${d.date}: ${d.views} views · ${d.enrollments} enrolls · ${d.completions} completes`}>
              <div className="bg-emerald-500 rounded-sm" style={{ height: `${(d.completions / maxDaily) * 100}%` }} />
              <div className="bg-indigo-500 rounded-sm" style={{ height: `${(d.enrollments / maxDaily) * 100}%` }} />
              <div className="bg-slate-300 rounded-sm" style={{ height: `${(d.views / maxDaily) * 100}%` }} />
            </div>
          ))}
        </div>
        <div className="flex items-center gap-4 mt-2 text-[10px] text-slate-500">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-300 inline-block" /> Views</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-indigo-500 inline-block" /> Enrols</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> Completes</span>
        </div>
      </div>
    </div>
  )
}

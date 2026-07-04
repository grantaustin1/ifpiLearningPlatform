import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { BarChart3, Eye, GraduationCap, Trophy, TrendingUp, TrendingDown, Loader2, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react'

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

interface DropoffData {
  course_id: number
  course_title: string
  days_window: number
  baseline_viewers: number
  slides: {
    slide_id: number
    order_index: number
    title: string
    unique_viewers: number
    retention: number
    step_dropoff: number
  }[]
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
  const [dropoff, setDropoff] = useState<DropoffData | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)
  // Iter 27 — Collapsible sections. Trend defaults collapsed (density);
  // drop-off defaults expanded (higher signal). Persist per-user in
  // localStorage so a habitual instructor's layout survives reloads.
  const [showTrend, setShowTrend] = useState<boolean>(
    () => localStorage.getItem('funnel-show-trend') !== '0'
  )
  const [showDropoff, setShowDropoff] = useState<boolean>(
    () => localStorage.getItem('funnel-show-dropoff') !== '0'
  )
  const toggleTrend = () => setShowTrend(v => {
    localStorage.setItem('funnel-show-trend', v ? '0' : '1'); return !v
  })
  const toggleDropoff = () => setShowDropoff(v => {
    localStorage.setItem('funnel-show-dropoff', v ? '0' : '1'); return !v
  })

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.get(`/admin/marketplace-funnel/${courseId}`, { params: { days } }),
      api.get(`/admin/course-dropoff/${courseId}`, { params: { days } }),
    ])
      .then(([f, d]) => { setData(f.data); setDropoff(d.data) })
      .catch(() => { setData(null); setDropoff(null) })
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

      {/* Sparkline — collapsible */}
      <div>
        <button onClick={toggleTrend} data-testid="toggle-funnel-trend"
          className="flex items-center gap-1 text-[11px] uppercase font-medium tracking-wide text-slate-400 mb-2 hover:text-slate-600 transition-colors">
          {showTrend ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          Daily trend
        </button>
        {showTrend && (<>
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
        </>)}
      </div>

      {/* Iter 26 — Slide-level drop-off heatmap (Iter 27 — collapsible) */}
      {dropoff && dropoff.slides.length > 0 && (
        <div className="mt-6 pt-5 border-t border-slate-100" data-testid="slide-dropoff-block">
          <div className="flex items-center justify-between mb-3">
            <button onClick={toggleDropoff} data-testid="toggle-slide-dropoff"
              className="flex items-center gap-1 text-[11px] uppercase font-medium tracking-wide text-slate-500 hover:text-slate-700 transition-colors">
              {showDropoff ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Slide drop-off
            </button>
            {showDropoff && (
              <span className="text-[10px] text-slate-400">baseline: {dropoff.baseline_viewers} viewers</span>
            )}
          </div>
          {showDropoff && (dropoff.baseline_viewers === 0 ? (
            <p className="text-xs text-slate-400 py-2" data-testid="slide-dropoff-empty">
              No slide-view data yet. Learners must play the course for tracking to appear.
            </p>
          ) : (
            <ul className="space-y-1.5" data-testid="slide-dropoff-list">
              {dropoff.slides.map(s => {
                const pct = Math.max(0, Math.min(100, s.retention * 100))
                const isSevereDrop = s.step_dropoff > 0.5 && s.order_index > 0
                return (
                  <li key={s.slide_id} className="flex items-center gap-2 text-xs"
                    data-testid={`slide-dropoff-row-${s.slide_id}`}>
                    <span className="w-5 text-right text-slate-400 tabular-nums">{s.order_index + 1}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        {isSevereDrop && (
                          <AlertTriangle className="h-3 w-3 text-amber-500 shrink-0"
                            data-testid={`slide-dropoff-warning-${s.slide_id}`} />
                        )}
                        <span className={`truncate ${isSevereDrop ? 'text-amber-700 font-medium' : 'text-slate-600'}`}>
                          {s.title || `Slide ${s.order_index + 1}`}
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={`h-2 rounded-full ${isSevereDrop ? 'bg-amber-400' : pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-indigo-500' : 'bg-slate-400'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                    <span className="w-14 text-right tabular-nums text-slate-500">
                      {s.unique_viewers} · {(s.retention * 100).toFixed(0)}%
                    </span>
                  </li>
                )
              })}
            </ul>
          ))}
        </div>
      )}
    </div>
  )
}

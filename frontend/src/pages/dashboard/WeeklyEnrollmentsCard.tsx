import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { TrendingUp } from 'lucide-react'

const METRICS = [
  { value: 'enrollments', label: 'Enrolments' },
  { value: 'completions', label: 'Completions' },
]

export function WeeklyEnrollmentsCard() {
  const [metric, setMetric] = useState('enrollments')
  const { data } = useQuery({
    queryKey: ['enrollments-weekly', metric],
    queryFn: async () => (await api.get('/admin/analytics/enrollments-weekly', { params: { metric } })).data,
  })
  const weeks: { week_start: string; count: number }[] = data?.weeks || []
  const max = Math.max(1, ...weeks.map(w => w.count))
  const total = weeks.reduce((s, w) => s + w.count, 0)
  const noun = metric === 'completions' ? 'completion' : 'enrolment'

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5" data-testid="weekly-enrollments-chart">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-indigo-500" /> Weekly {noun}s
        </h3>
        <div className="flex rounded-lg border border-slate-200 p-0.5" data-testid="weekly-metric-toggle">
          {METRICS.map(m => (
            <button key={m.value} onClick={() => setMetric(m.value)}
              data-testid={`weekly-metric-${m.value}`}
              className={`text-[11px] font-medium px-2 py-1 rounded-md transition-colors ${metric === m.value ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-slate-700'}`}>
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-slate-400 mb-4">{total} in the last {weeks.length} weeks</p>
      {weeks.length === 0 ? (
        <p className="text-xs text-slate-400">No data yet.</p>
      ) : (
        <div className="flex items-end gap-1.5 h-28" data-testid="weekly-enrollments-bars">
          {weeks.map(w => {
            const d = new Date(w.week_start + 'T00:00:00')
            const label = d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
            return (
              <div key={w.week_start} className="flex-1 flex flex-col items-center gap-1 group"
                title={`Week of ${label}: ${w.count} ${noun}${w.count === 1 ? '' : 's'}`}>
                <span className="text-[9px] text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity">{w.count}</span>
                <div
                  className={`w-full rounded-t-md transition-colors ${w.count > 0 ? 'bg-indigo-500 group-hover:bg-indigo-600' : 'bg-slate-100'}`}
                  style={{ height: `${Math.max(4, (w.count / max) * 88)}px` }}
                />
                <span className="text-[8px] text-slate-400 whitespace-nowrap">{label}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

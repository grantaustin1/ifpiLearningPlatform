import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { TrendingUp } from 'lucide-react'

export function WeeklyEnrollmentsCard() {
  const { data } = useQuery({
    queryKey: ['enrollments-weekly'],
    queryFn: async () => (await api.get('/admin/analytics/enrollments-weekly')).data,
  })
  const weeks: { week_start: string; count: number }[] = data?.weeks || []
  const max = Math.max(1, ...weeks.map(w => w.count))
  const total = weeks.reduce((s, w) => s + w.count, 0)

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5" data-testid="weekly-enrollments-chart">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-indigo-500" /> Weekly enrolments
        </h3>
        <span className="text-xs text-slate-400">{total} in the last {weeks.length} weeks</span>
      </div>
      {weeks.length === 0 ? (
        <p className="text-xs text-slate-400">No data yet.</p>
      ) : (
        <div className="flex items-end gap-1.5 h-28" data-testid="weekly-enrollments-bars">
          {weeks.map(w => {
            const d = new Date(w.week_start + 'T00:00:00')
            const label = d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
            return (
              <div key={w.week_start} className="flex-1 flex flex-col items-center gap-1 group"
                title={`Week of ${label}: ${w.count} enrolment${w.count === 1 ? '' : 's'}`}>
                <span className="text-[9px] text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity">{w.count}</span>
                <div
                  className={`w-full rounded-t-md transition-colors ${w.count > 0 ? 'bg-indigo-500 group-hover:bg-indigo-600' : 'bg-slate-100'}`}
                  style={{ height: `${Math.max(4, (w.count / max) * 88)}px` }}
                />
                <span className="text-[8px] text-slate-400 rotate-0 whitespace-nowrap">{label}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

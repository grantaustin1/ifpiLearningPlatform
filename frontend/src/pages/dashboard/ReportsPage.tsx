import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Users, BookOpen, Award, ClipboardList } from 'lucide-react'
import { timeAgo } from 'lib/utils'

export default function ReportsPage() {
  const { data, isLoading } = useQuery<any>({
    queryKey: ['analytics'], queryFn: async () => (await api.get('/admin/analytics')).data,
  })

  if (isLoading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>
  if (!data) return <div className="p-8 text-slate-400">Failed to load analytics.</div>

  const stats = [
    { label: 'Learners',     value: data.total_learners,     icon: Users,         color: 'text-indigo-600', bg: 'bg-indigo-50' },
    { label: 'Courses',      value: data.total_courses,      icon: BookOpen,      color: 'text-violet-600', bg: 'bg-violet-50' },
    { label: 'Certificates', value: data.total_certificates, icon: Award,         color: 'text-amber-600',  bg: 'bg-amber-50' },
    { label: 'Exam Attempts',value: data.total_exam_attempts,icon: ClipboardList, color: 'text-emerald-600',bg: 'bg-emerald-50' },
  ]

  const maxMonthly = Math.max(...(data.monthly_enrollments || []).map((m: any) => m.count), 1)

  return (
    <div className="p-8 space-y-6" data-testid="reports-page">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 font-display">Analytics</h1>
        <p className="text-slate-500 mt-1">Platform overview and learner progress</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(s => (
          <div key={s.label} className="bg-white rounded-2xl shadow-sm p-5 flex items-center gap-4">
            <div className={`p-2.5 rounded-xl ${s.bg}`}><s.icon className={`h-5 w-5 ${s.color}`} /></div>
            <div><p className="text-2xl font-bold text-slate-900">{s.value.toLocaleString()}</p><p className="text-xs text-slate-500 mt-1">{s.label}</p></div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm p-5">
          <h2 className="text-sm font-semibold text-slate-800 mb-4">Monthly Enrolments</h2>
          <div className="flex items-end gap-3 h-32">
            {(data.monthly_enrollments || []).map((m: any, i: number) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full bg-indigo-500 rounded-t-md transition-all" style={{ height: `${m.count > 0 ? Math.max((m.count / maxMonthly) * 100, 8) : 2}%` }} title={`${m.count} enrolment(s)`} />
                <span className="text-[10px] text-slate-400">{m.month}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-white rounded-2xl shadow-sm p-5">
          <h2 className="text-sm font-semibold text-slate-800 mb-4">Completion & Score</h2>
          <div className="flex justify-around items-center h-32">
            <Donut pct={data.completion_rate} color="#6366f1" label="Completion" />
            <Donut pct={data.avg_exam_score} color="#10b981" label="Avg Score" />
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-50"><h2 className="text-sm font-semibold text-slate-800">Top Courses</h2></div>
          <div className="divide-y divide-slate-50">
            {data.top_courses?.length === 0 ? <p className="py-10 text-center text-slate-300 text-sm">No data</p> :
             data.top_courses?.map((c: any) => (
              <div key={c.id} className="px-5 py-3.5 flex items-center gap-3">
                <div className="flex-1 min-w-0"><p className="text-sm font-medium truncate">{c.title}</p><p className="text-xs text-slate-400">{c.total} enrolled · {c.completed} completed</p></div>
                <div className="flex items-center gap-2"><div className="w-20 h-1.5 bg-slate-100 rounded-full overflow-hidden"><div className="h-full bg-indigo-500" style={{ width: `${c.rate}%` }} /></div><span className="text-xs font-semibold w-9 text-right">{c.rate}%</span></div>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-50"><h2 className="text-sm font-semibold text-slate-800">Recent Enrolments</h2></div>
          <div className="divide-y divide-slate-50 max-h-72 overflow-y-auto">
            {data.recent_activity?.map((a: any, i: number) => (
              <div key={i} className="px-5 py-3">
                <p className="text-sm font-medium text-slate-700">{a.user_name}</p>
                <p className="text-xs text-slate-400 truncate">{a.course_title}</p>
                <p className="text-[10px] text-slate-300 mt-1">{timeAgo(a.enrolled_at)}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function Donut({ pct, color, label }: any) {
  const r = 40, circ = 2 * Math.PI * r, dash = (pct / 100) * circ
  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#e5e7eb" strokeWidth="12" />
        <circle cx="50" cy="50" r={r} fill="none" stroke={color} strokeWidth="12"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" transform="rotate(-90 50 50)" />
        <text x="50" y="50" textAnchor="middle" dominantBaseline="central" fontSize="18" fontWeight="700" fill="#0f172a">{pct}%</text>
      </svg>
      <span className="text-xs text-slate-500">{label}</span>
    </div>
  )
}

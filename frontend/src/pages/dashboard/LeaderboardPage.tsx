import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Trophy, Star, Award, CheckCircle, Layers } from 'lucide-react'
import { useAuth } from 'contexts/AuthContext'

export default function LeaderboardPage() {
  const { user } = useAuth()
  const isAdmin = (user?.roles || []).some((r: string) => ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(r))
  const [cohort, setCohort] = useState('')

  const { data: rows = [] } = useQuery<any[]>({
    queryKey: ['leaderboard', cohort],
    queryFn: async () => (await api.get('/gamification/leaderboard', {
      params: { cohort: cohort || undefined },
    })).data,
  })
  const { data: me } = useQuery<any>({
    queryKey: ['gam-me'], queryFn: async () => (await api.get('/gamification/me')).data,
  })
  const { data: cohorts = [] } = useQuery<any[]>({
    queryKey: ['cohorts'],
    queryFn: async () => (await api.get('/admin/cohorts')).data,
    enabled: isAdmin,
  })

  return (
    <div className="p-8 space-y-6" data-testid="leaderboard-page">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">Leaderboard</h1>
          <p className="text-slate-500 mt-1">Top learners by XP{cohort && <span> · cohort <span className="font-semibold text-indigo-600">{cohort}</span></span>}</p>
        </div>
        {isAdmin && cohorts.length > 0 && (
          <select value={cohort} onChange={e => setCohort(e.target.value)} data-testid="leaderboard-cohort"
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white">
            <option value="">All learners</option>
            {cohorts.map((c: any) => (
              <option key={c.cohort} value={c.cohort}>{c.cohort} ({c.learner_count})</option>
            ))}
          </select>
        )}
      </div>

      {me && (
        <div className="bg-gradient-to-r from-indigo-500 to-violet-600 rounded-2xl p-5 text-white" data-testid="my-rank-card">
          <div className="flex items-center gap-6">
            <div><p className="text-3xl font-bold">#{me.rank}</p><p className="text-xs opacity-80">of {me.total}</p></div>
            <div className="h-12 w-px bg-white/20" />
            <div><p className="text-3xl font-bold flex items-center gap-1"><Star className="h-6 w-6 fill-amber-300 text-amber-300" />{me.points}</p><p className="text-xs opacity-80">XP earned</p></div>
            <div className="h-12 w-px bg-white/20" />
            <div><p className="text-3xl font-bold">{me.badges?.length || 0}</p><p className="text-xs opacity-80">Badges</p></div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b"><tr>
            <th className="text-left px-6 py-3 font-medium text-slate-500">Rank</th>
            <th className="text-left px-6 py-3 font-medium text-slate-500">Learner</th>
            <th className="text-right px-6 py-3 font-medium text-slate-500">XP</th>
            <th className="text-right px-6 py-3 font-medium text-slate-500">Badges</th>
            <th className="text-right px-6 py-3 font-medium text-slate-500">Completed</th>
          </tr></thead>
          <tbody className="divide-y">
            {rows.map((r: any, i: number) => (
              <tr key={r.user_id} data-testid={`lb-row-${i}`}>
                <td className="px-6 py-4">
                  {i < 3 ? <Trophy className={`h-5 w-5 ${i === 0 ? 'text-amber-500' : i === 1 ? 'text-slate-400' : 'text-amber-700'}`} /> : <span className="text-slate-500 font-semibold">#{i + 1}</span>}
                </td>
                <td className="px-6 py-4 font-medium">{r.name || `Learner #${r.user_id}`}</td>
                <td className="px-6 py-4 text-right"><span className="inline-flex items-center gap-1 font-semibold"><Star className="h-3.5 w-3.5 text-amber-500" />{r.points}</span></td>
                <td className="px-6 py-4 text-right"><span className="inline-flex items-center gap-1 text-slate-600"><Award className="h-3.5 w-3.5" />{r.badges}</span></td>
                <td className="px-6 py-4 text-right"><span className="inline-flex items-center gap-1 text-slate-600"><CheckCircle className="h-3.5 w-3.5" />{r.completed}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { Flame, Trophy, X } from 'lucide-react'

interface LeaderEntry {
  user_id: number
  name: string
  current_streak: number
  longest_streak: number
  active_today: boolean
  is_you: boolean
}

interface Leaderboard {
  top: LeaderEntry[]
  your_rank: number | null
  your_entry: LeaderEntry | null
  total_participants: number
}

/**
 * Iter 28 — Org-wide "top streaks this week" leaderboard.
 *
 * A compact link-styled trigger next to the streak badge that opens a
 * modal with the ranked list. Silently hides if the caller's org has
 * no active learners (fresh org edge case).
 */
export function StreakLeaderboardModal({ onClose }: { onClose: () => void }) {
  const [board, setBoard] = useState<Leaderboard | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/gamification/streak-leaderboard', { params: { limit: 10 } })
      .then(r => setBoard(r.data))
      .catch(() => setBoard(null))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      data-testid="streak-leaderboard-modal" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-amber-500" />
            <div>
              <h2 className="font-semibold text-slate-900">Top streaks this week</h2>
              {board && (
                <p className="text-xs text-slate-500 mt-0.5">
                  {board.total_participants} active learner{board.total_participants === 1 ? '' : 's'} in your org
                </p>
              )}
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"
            data-testid="close-streak-leaderboard">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5">
          {loading ? (
            <p className="text-sm text-slate-400 text-center py-8">Loading…</p>
          ) : !board || board.top.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-8" data-testid="streak-leaderboard-empty">
              No streaks in your org yet. Be the first — view a slide today!
            </p>
          ) : (
            <ol className="space-y-1.5" data-testid="streak-leaderboard-list">
              {board.top.map((e, i) => (
                <li key={e.user_id}
                  data-testid={`streak-leader-row-${e.user_id}`}
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg
                    ${e.is_you ? 'bg-indigo-50 border border-indigo-200' : ''}`}>
                  <span className={`w-6 text-center font-semibold tabular-nums
                    ${i === 0 ? 'text-amber-500' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-orange-600' : 'text-slate-300'}`}>
                    {i + 1}
                  </span>
                  <span className="flex-1 truncate text-sm text-slate-800">
                    {e.name}{e.is_you && <span className="ml-1 text-xs text-indigo-600 font-medium">(you)</span>}
                  </span>
                  <span className={`inline-flex items-center gap-1 text-xs font-semibold
                    ${e.active_today ? 'text-orange-600' : 'text-amber-600'}`}>
                    <Flame className="h-3.5 w-3.5" />
                    {e.current_streak}d
                  </span>
                </li>
              ))}
            </ol>
          )}

          {board && board.your_rank && board.your_rank > board.top.length && board.your_entry && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <p className="text-xs text-slate-400 mb-2">Your rank</p>
              <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-indigo-50 border border-indigo-200"
                data-testid="streak-leaderboard-your-rank">
                <span className="w-6 text-center font-semibold tabular-nums text-slate-500">{board.your_rank}</span>
                <span className="flex-1 truncate text-sm text-slate-800">
                  {board.your_entry.name} <span className="ml-1 text-xs text-indigo-600 font-medium">(you)</span>
                </span>
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-orange-600">
                  <Flame className="h-3.5 w-3.5" /> {board.your_entry.current_streak}d
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


export function StreakLeaderboardTrigger() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        data-testid="open-streak-leaderboard"
        className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-orange-600 transition-colors"
        title="Org-wide streak leaderboard"
      >
        <Trophy className="h-3.5 w-3.5" />
        Leaderboard
      </button>
      {open && <StreakLeaderboardModal onClose={() => setOpen(false)} />}
    </>
  )
}

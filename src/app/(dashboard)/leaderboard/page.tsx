"use client"

import { useState, useEffect } from "react"
import { Trophy, BookOpen, Award } from "lucide-react"
import { useSession } from "next-auth/react"
import { BADGE_META } from "@/lib/gamification"

interface LeaderEntry {
  id: string; name: string | null; points: number
  badges: { badge: string; earnedAt: string }[]
  _count: { enrollments: number; certificates: number }
}

function RankMedal({ rank }: { rank: number }) {
  if (rank === 1) return <span className="text-xl">🥇</span>
  if (rank === 2) return <span className="text-xl">🥈</span>
  if (rank === 3) return <span className="text-xl">🥉</span>
  return (
    <span className="w-7 h-7 rounded-full bg-slate-100 text-slate-500 text-xs font-bold flex items-center justify-center">
      {rank}
    </span>
  )
}

export default function LeaderboardPage() {
  const { data: session } = useSession()
  const [learners, setLearners] = useState<LeaderEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch("/api/leaderboard")
      .then(r => r.json())
      .then(data => { setLearners(Array.isArray(data) ? data : []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
          <Trophy className="h-5 w-5 text-amber-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Leaderboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">Top learners ranked by XP points</p>
        </div>
      </div>

      {learners.length >= 3 && (
        <div className="grid grid-cols-3 gap-3">
          {[1, 0, 2].map(idx => {
            const l = learners[idx]
            if (!l) return null
            const rank = idx + 1
            const isYou = l.id === session?.user?.id
            return (
              <div
                key={l.id}
                className={[
                  "rounded-2xl p-4 text-center border",
                  rank === 1 ? "bg-amber-50 border-amber-200 shadow-md" : rank === 2 ? "bg-slate-50 border-slate-200" : "bg-orange-50 border-orange-200",
                  idx === 0 ? "order-2" : idx === 1 ? "order-1" : "order-3",
                  isYou ? "ring-2 ring-indigo-400" : "",
                ].join(" ")}
              >
                <div className="text-2xl mb-1">{rank === 1 ? "🥇" : rank === 2 ? "🥈" : "🥉"}</div>
                <p className="text-sm font-bold text-slate-800 truncate">{l.name ?? "Learner"}{isYou ? " (you)" : ""}</p>
                <p className="text-xs text-slate-500 mt-0.5">{l.points.toLocaleString()} XP</p>
              </div>
            )
          })}
        </div>
      )}

      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="divide-y divide-slate-50">
          {learners.length === 0 ? (
            <div className="py-12 text-center text-sm text-slate-400">
              No learners yet — complete courses and exams to earn XP!
            </div>
          ) : learners.map((l, idx) => {
            const isYou = l.id === session?.user?.id
            return (
              <div key={l.id} className={`flex items-center gap-4 px-5 py-3.5 ${isYou ? "bg-indigo-50" : "hover:bg-slate-50"} transition-colors`}>
                <div className="w-8 flex items-center justify-center flex-shrink-0">
                  <RankMedal rank={idx + 1} />
                </div>
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center flex-shrink-0">
                  <span className="text-[10px] font-bold text-white">
                    {(l.name ?? "?").split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800 truncate">
                    {l.name ?? "Learner"}{isYou ? " (you)" : ""}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[11px] text-slate-400 flex items-center gap-1">
                      <BookOpen style={{ width: 10, height: 10 }} /> {l._count.enrollments}
                    </span>
                    <span className="text-[11px] text-slate-400 flex items-center gap-1">
                      <Award style={{ width: 10, height: 10 }} /> {l._count.certificates}
                    </span>
                  </div>
                </div>
                <div className="flex gap-1 flex-wrap justify-end max-w-[72px]">
                  {l.badges.slice(0, 3).map(b => (
                    <span key={b.badge} title={BADGE_META[b.badge]?.label ?? b.badge} className="text-base">
                      {BADGE_META[b.badge]?.emoji ?? "🏅"}
                    </span>
                  ))}
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-sm font-bold text-slate-900">{l.points.toLocaleString()}</p>
                  <p className="text-[10px] text-slate-400">XP</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

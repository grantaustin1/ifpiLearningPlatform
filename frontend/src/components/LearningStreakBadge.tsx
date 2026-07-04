import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { Flame } from 'lucide-react'

interface Streak {
  current_streak: number
  longest_streak: number
  active_today: boolean
  last_active_date: string | null
}

/**
 * Iter 26 — Learner-side streak badge.
 *
 * Renders a compact "🔥 N-day streak" chip when the learner has an
 * active streak. Silently hides on 0 (no shame for new learners) and
 * gently nudges idle-today learners with a muted variant.
 *
 * Data is powered by /api/gamification/learning-streak which fuses
 * SlideView + FlashcardReview activity dates — so simply opening a
 * course slide counts as "active today".
 */
export function LearningStreakBadge() {
  const [streak, setStreak] = useState<Streak | null>(null)

  useEffect(() => {
    api.get('/gamification/learning-streak')
      .then(r => setStreak(r.data))
      .catch(() => setStreak(null))
  }, [])

  if (!streak || streak.current_streak <= 0) return null
  const idleToday = !streak.active_today
  return (
    <div
      data-testid="learning-streak-badge"
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold
        ${idleToday
          ? 'bg-amber-50 text-amber-700 border border-amber-200'
          : 'bg-orange-100 text-orange-700 border border-orange-200'}`}
      title={
        idleToday
          ? `Come back today to keep your ${streak.current_streak}-day streak alive`
          : `You're on a ${streak.current_streak}-day learning streak — longest ever: ${streak.longest_streak}d`
      }
    >
      <Flame className={`h-3.5 w-3.5 ${idleToday ? 'text-amber-500' : 'text-orange-500'}`} />
      <span data-testid="learning-streak-count">
        {streak.current_streak}-day streak
      </span>
      {streak.longest_streak > streak.current_streak && (
        <span className="text-[10px] font-normal opacity-70" data-testid="learning-streak-best">
          · best {streak.longest_streak}d
        </span>
      )}
    </div>
  )
}

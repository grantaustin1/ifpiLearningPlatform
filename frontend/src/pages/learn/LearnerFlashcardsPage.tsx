import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from 'lib/api'
import { Sparkles, Loader2, Eye, ChevronLeft, ChevronRight, ArrowLeft, List, Layers } from 'lucide-react'
import { toast } from 'sonner'

interface Card {
  id: number
  front: string
  back: string
  hint?: string | null
  difficulty: number
  tags: string[]
  review: null | {
    ease_factor: number
    interval_days: number
    repetitions: number
    next_review_at: string
    last_quality: number | null
    review_count: number
  }
}
interface Stats {
  total: number; new: number; learning: number; mastered: number; due_now: number
}
interface Streak {
  current_streak: number; longest_streak: number; reviewed_today: boolean
}

const QUALITY_LABELS: Array<{ q: number; label: string; color: string; hint: string }> = [
  { q: 0, label: 'Blackout', color: 'bg-rose-600 hover:bg-rose-700', hint: 'No idea' },
  { q: 1, label: 'Hard',     color: 'bg-rose-500 hover:bg-rose-600', hint: 'Wrong, remembered' },
  { q: 2, label: 'Wrong',    color: 'bg-orange-500 hover:bg-orange-600', hint: 'Almost right' },
  { q: 3, label: 'Okay',     color: 'bg-amber-500 hover:bg-amber-600', hint: 'Correct, hesitated' },
  { q: 4, label: 'Good',     color: 'bg-lime-500 hover:bg-lime-600', hint: 'Fluent' },
  { q: 5, label: 'Perfect',  color: 'bg-emerald-600 hover:bg-emerald-700', hint: 'Instant recall' },
]

export default function LearnerFlashcardsPage() {
  const { courseId } = useParams()
  const nav = useNavigate()
  const cid = Number(courseId)
  const [cards, setCards] = useState<Card[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [streak, setStreak] = useState<Streak | null>(null)
  const [lastXp, setLastXp] = useState<{ xp: number; bonus: boolean } | null>(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<'swipe' | 'list'>('swipe')
  const [i, setI] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [d, s, st] = await Promise.all([
        api.get(`/learn/flashcards/courses/${cid}/due`),
        api.get(`/learn/flashcards/courses/${cid}/stats`),
        api.get('/learn/flashcards/streak'),
      ])
      setCards(d.data.cards || [])
      setStats(s.data)
      setStreak(st.data)
      setI(0); setFlipped(false)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [cid]) // eslint-disable-line react-hooks/exhaustive-deps

  const current = cards[i]
  const done = !loading && cards.length > 0 && i >= cards.length

  const submitReview = useCallback(async (quality: number) => {
    if (!current || submitting) return
    setSubmitting(true)
    try {
      const r = await api.post(`/learn/flashcards/${current.id}/review`, { quality })
      const xp = r.data.xp_awarded || 0
      if (xp > 0) {
        setLastXp({ xp, bonus: !!r.data.streak_bonus_applied })
        setTimeout(() => setLastXp(null), 2500)
      }
      if (r.data.streak) setStreak(r.data.streak)
      // Advance
      if (i + 1 >= cards.length) {
        setI(cards.length)
        toast.success('Session complete!')
      } else {
        setI(i + 1)
        setFlipped(false)
      }
    } catch (e: any) {
      toast.error(String(e?.response?.data?.detail ?? 'Review failed'))
    } finally { setSubmitting(false) }
  }, [current, submitting, i, cards.length])

  // Keyboard shortcuts (1-5 rate, Space flip)
  useEffect(() => {
    if (mode !== 'swipe') return
    const onKey = (e: KeyboardEvent) => {
      if (e.code === 'Space') { e.preventDefault(); setFlipped(f => !f); return }
      if (!flipped) return
      const q = parseInt(e.key, 10)
      if (Number.isFinite(q) && q >= 0 && q <= 5) submitReview(q)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mode, flipped, submitReview])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50/30">
      <div className="p-8 max-w-4xl mx-auto space-y-6">
        <button onClick={() => nav(`/learn/${cid}`)} className="text-xs text-indigo-600 hover:underline inline-flex items-center gap-1" data-testid="lfc-back-btn">
          <ArrowLeft className="h-3 w-3" /> Back to course
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
              <Sparkles className="text-indigo-500" /> Flashcards
            </h1>
            <p className="text-slate-500 text-sm mt-1">
              Spaced repetition — the more you review, the longer between reviews.
            </p>
          </div>
          <div className="flex items-center gap-2 bg-white rounded-lg border border-slate-200 p-1">
            <button onClick={() => setMode('swipe')}
              data-testid="lfc-mode-swipe"
              className={`px-3 py-1.5 text-xs font-semibold rounded flex items-center gap-1.5 ${mode === 'swipe' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-50'}`}>
              <Layers className="h-3.5 w-3.5" /> Swipe
            </button>
            <button onClick={() => setMode('list')}
              data-testid="lfc-mode-list"
              className={`px-3 py-1.5 text-xs font-semibold rounded flex items-center gap-1.5 ${mode === 'list' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-50'}`}>
              <List className="h-3.5 w-3.5" /> List
            </button>
          </div>
        </div>

        {streak && (
          <div className="flex items-center gap-3" data-testid="lfc-streak">
            <div className={`rounded-2xl px-4 py-3 flex items-center gap-3 border-2 ${streak.current_streak > 0 ? 'bg-orange-50 border-orange-200' : 'bg-slate-50 border-slate-200'}`}>
              <span className="text-2xl">{streak.current_streak > 0 ? '🔥' : '💤'}</span>
              <div>
                <div className="text-xl font-bold tabular-nums text-slate-800">{streak.current_streak}-day streak</div>
                <div className="text-[11px] text-slate-500">Longest: {streak.longest_streak} · {streak.reviewed_today ? 'Reviewed today ✓' : 'Review one card to keep it alive'}</div>
              </div>
            </div>
            {lastXp && (
              <div className="rounded-full px-3 py-1.5 bg-emerald-100 text-emerald-800 text-xs font-bold animate-pulse" data-testid="lfc-xp-flash">
                +{lastXp.xp} XP {lastXp.bonus ? '· 🔥 streak bonus!' : ''}
              </div>
            )}
          </div>
        )}

        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="lfc-stats">
            {[
              { k: 'Total',     v: stats.total,     tone: 'bg-slate-100 text-slate-700' },
              { k: 'Due now',   v: stats.due_now,   tone: 'bg-amber-100 text-amber-800' },
              { k: 'New',       v: stats.new,       tone: 'bg-sky-100 text-sky-800' },
              { k: 'Learning',  v: stats.learning,  tone: 'bg-violet-100 text-violet-800' },
              { k: 'Mastered',  v: stats.mastered,  tone: 'bg-emerald-100 text-emerald-800' },
            ].map(s => (
              <div key={s.k} className={`rounded-xl p-3 ${s.tone}`}>
                <div className="text-2xl font-bold">{s.v}</div>
                <div className="text-[11px] uppercase tracking-wide opacity-70">{s.k}</div>
              </div>
            ))}
          </div>
        )}

        {loading ? (
          <div className="text-sm text-slate-500 flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
        ) : cards.length === 0 ? (
          <div className="bg-white rounded-2xl border border-dashed border-slate-300 py-16 text-center">
            <p className="text-slate-600 font-medium">Nothing to review right now 🎉</p>
            <p className="text-slate-500 text-sm mt-1">Come back later — new cards will appear based on your review history.</p>
          </div>
        ) : mode === 'swipe' ? (
          done ? (
            <div className="bg-white rounded-2xl border border-emerald-200 py-16 text-center" data-testid="lfc-session-done">
              <div className="text-4xl mb-3">🎯</div>
              <p className="text-slate-800 font-semibold">Session complete!</p>
              <p className="text-slate-500 text-sm mt-1">You reviewed {cards.length} cards. Great work.</p>
              <button onClick={load} className="mt-4 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-5 py-2 rounded-lg">
                Refresh queue
              </button>
            </div>
          ) : current && (
            <>
              <div className="text-center text-xs text-slate-500 tabular-nums">
                Card {i + 1} of {cards.length}
              </div>
              <div
                className="bg-white rounded-2xl border border-slate-200 shadow-xl min-h-[300px] cursor-pointer flex flex-col items-center justify-center p-10 text-center transition-transform hover:scale-[1.005]"
                onClick={() => setFlipped(f => !f)}
                data-testid="lfc-card"
              >
                <div className="text-[11px] uppercase tracking-widest text-slate-400 mb-4">
                  {flipped ? 'Answer' : 'Question'}
                </div>
                <p className="text-2xl font-semibold text-slate-800 whitespace-pre-wrap">
                  {flipped ? current.back : current.front}
                </p>
                {!flipped && current.hint && (
                  <p className="mt-4 text-xs text-slate-500 italic">Hint: {current.hint}</p>
                )}
                {!flipped && (
                  <button className="mt-6 inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600" data-testid="lfc-show-answer">
                    <Eye className="h-3.5 w-3.5" /> Reveal (Space)
                  </button>
                )}
              </div>

              {flipped ? (
                <div className="grid grid-cols-3 md:grid-cols-6 gap-2" data-testid="lfc-rating-row">
                  {QUALITY_LABELS.map(({ q, label, color, hint }) => (
                    <button key={q}
                      onClick={() => submitReview(q)}
                      disabled={submitting}
                      data-testid={`lfc-rate-${q}`}
                      className={`${color} text-white rounded-xl py-3 px-2 text-xs font-bold disabled:opacity-60 transition`}
                    >
                      <div className="text-lg leading-none">{q}</div>
                      <div className="mt-1">{label}</div>
                      <div className="text-[10px] font-normal opacity-80 mt-0.5">{hint}</div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <button onClick={() => { if (i > 0) { setI(i - 1); setFlipped(false) } }}
                    disabled={i === 0}
                    className="inline-flex items-center gap-1 disabled:opacity-40" data-testid="lfc-prev">
                    <ChevronLeft className="h-3.5 w-3.5" /> Prev
                  </button>
                  <span>Space to flip · 1-5 to rate</span>
                  <button onClick={() => { if (i < cards.length - 1) { setI(i + 1); setFlipped(false) } }}
                    disabled={i >= cards.length - 1}
                    className="inline-flex items-center gap-1 disabled:opacity-40" data-testid="lfc-next">
                    Next <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
            </>
          )
        ) : (
          <div className="space-y-3" data-testid="lfc-list-view">
            {cards.map((c, idx) => (
              <ListRow key={c.id} card={c} idx={idx} onReview={submitReview} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ListRow({ card, idx, onReview }:
  { card: Card; idx: number; onReview: (q: number) => void }) {
  const [revealed, setRevealed] = useState(false)
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid={`lfc-list-card-${idx}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <p className="text-sm font-semibold text-slate-800">{card.front}</p>
          {revealed ? (
            <p className="mt-2 text-sm text-slate-600 whitespace-pre-wrap">{card.back}</p>
          ) : (
            <button onClick={() => setRevealed(true)}
              data-testid={`lfc-list-reveal-${idx}`}
              className="mt-2 text-xs font-semibold text-indigo-600 inline-flex items-center gap-1">
              <Eye className="h-3.5 w-3.5" /> Reveal answer
            </button>
          )}
        </div>
        <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wide">D{card.difficulty}</span>
      </div>
      {revealed && (
        <div className="mt-3 grid grid-cols-6 gap-1.5">
          {QUALITY_LABELS.map(({ q, label, color }) => (
            <button key={q} onClick={() => { onReview(q); setRevealed(false) }}
              data-testid={`lfc-list-rate-${idx}-${q}`}
              className={`${color} text-white rounded py-1.5 text-[10px] font-bold`}>
              {q} · {label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

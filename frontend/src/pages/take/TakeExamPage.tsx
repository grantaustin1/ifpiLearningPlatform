import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from 'lib/api'
import { Clock, CheckCircle, XCircle, ChevronLeft, ChevronRight, Star } from 'lucide-react'
import { toast } from 'sonner'

export default function TakeExamPage() {
  const { examId } = useParams()
  const nav = useNavigate()
  const [exam, setExam] = useState<any>(null)
  const [phase, setPhase] = useState<'intro' | 'taking' | 'submitting' | 'result'>('intro')
  const [current, setCurrent] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [timeLeft, setTimeLeft] = useState<number | null>(null)
  const [result, setResult] = useState<any>(null)

  useEffect(() => {
    api.get(`/exams/${examId}`).then(r => setExam(r.data))
  }, [examId])

  useEffect(() => {
    if (phase !== 'taking' || !exam?.time_limit_minutes) return
    setTimeLeft(exam.time_limit_minutes * 60)
  }, [phase, exam?.time_limit_minutes])

  const submit = useCallback(async () => {
    if (!exam) return
    setPhase('submitting')
    try {
      const r = await api.post(`/exams/${examId}/attempts`, { answers })
      setResult(r.data); setPhase('result')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Submission failed'); setPhase('taking')
    }
  }, [examId, answers, exam])

  useEffect(() => {
    if (timeLeft === null || phase !== 'taking') return
    if (timeLeft <= 0) { submit(); return }
    const t = setTimeout(() => setTimeLeft(tl => (tl ?? 1) - 1), 1000)
    return () => clearTimeout(t)
  }, [timeLeft, phase, submit])

  if (!exam) return <div className="flex items-center justify-center h-screen"><div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>

  const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`

  if (phase === 'intro') return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4" data-testid="exam-intro">
      <div className="max-w-lg w-full bg-white rounded-2xl shadow-xl p-8">
        <div className="text-center mb-6">
          <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4"><CheckCircle className="h-8 w-8 text-indigo-600" /></div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">{exam.title}</h1>
          {exam.description && <p className="text-slate-500 mt-2">{exam.description}</p>}
        </div>
        <div className="grid grid-cols-2 gap-4 mb-6">
          <Stat label="Questions" value={exam.questions.length} />
          <Stat label="Pass mark" value={`${exam.passing_score}%`} />
          {exam.time_limit_minutes && <Stat label="Time limit" value={`${exam.time_limit_minutes}m`} />}
          <Stat label="Attempts left" value={Math.max(0, exam.max_attempts - (exam.user_attempt_count || 0))} />
        </div>
        <button onClick={() => setPhase('taking')} data-testid="start-exam-btn"
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-lg">Start Exam</button>
      </div>
    </div>
  )

  if (phase === 'submitting') return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center"><div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" /><p className="text-slate-500">Grading…</p></div>
    </div>
  )

  if (phase === 'result' && result) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4" data-testid="exam-result">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center">
        <div className={`w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 ${result.passed ? 'bg-emerald-100' : 'bg-red-100'}`}>
          {result.passed ? <CheckCircle className="h-10 w-10 text-emerald-600" /> : <XCircle className="h-10 w-10 text-red-600" />}
        </div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2 font-display">{result.passed ? 'Congratulations!' : 'Not quite'}</h2>
        <p className="text-slate-500 mb-4">{result.passed ? 'You passed.' : `You need ${exam.passing_score}% to pass.`}</p>
        {result.xp_earned > 0 && (
          <div className="inline-flex items-center gap-1.5 bg-amber-50 border border-amber-200 text-amber-700 text-sm font-semibold px-3 py-1.5 rounded-full mb-4">
            <Star className="h-4 w-4" /> +{result.xp_earned} XP
          </div>
        )}
        <div className="w-32 h-32 relative mx-auto mb-6">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="45" fill="none" stroke="#e5e7eb" strokeWidth="10" />
            <circle cx="50" cy="50" r="45" fill="none" stroke={result.passed ? '#16a34a' : '#dc2626'} strokeWidth="10" strokeDasharray={`${result.score * 2.83} 283`} strokeLinecap="round" />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center"><span className="text-2xl font-bold">{result.score}%</span></div>
        </div>
        <button onClick={() => nav('/exams')} className="w-full bg-slate-100 hover:bg-slate-200 rounded-lg py-2.5 font-medium" data-testid="exam-back-btn">Back to Exams</button>
      </div>
    </div>
  )

  // taking
  const q = exam.questions[current]
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col" data-testid="exam-taking">
      <div className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <span className="font-semibold truncate max-w-xs">{exam.title}</span>
        <div className="flex items-center gap-4">
          {timeLeft !== null && <span className={`inline-flex items-center gap-1.5 font-mono font-semibold text-sm ${timeLeft < 60 ? 'text-red-600' : 'text-slate-700'}`}><Clock className="h-4 w-4" /> {fmt(timeLeft)}</span>}
          <span className="text-sm text-slate-500">{Object.keys(answers).length}/{exam.questions.length}</span>
        </div>
      </div>
      <div className="h-1 bg-slate-100"><div className="h-1 bg-indigo-600 transition-all" style={{ width: `${((current + 1) / exam.questions.length) * 100}%` }} /></div>
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="max-w-2xl w-full bg-white rounded-2xl shadow-lg p-8">
          <div className="flex items-start justify-between mb-6">
            <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full">Q {current + 1} of {exam.questions.length}</span>
            <span className="text-xs text-slate-400">{q.points} pt{q.points !== 1 ? 's' : ''}</span>
          </div>
          <h2 className="text-lg font-semibold mb-6 leading-relaxed" data-testid="question-text">{q.question_text}</h2>
          {q.question_type === 'MULTIPLE_CHOICE' && (
            <div className="space-y-3">
              {(q.options || []).map((opt: string, i: number) => (
                <button key={i} onClick={() => setAnswers(a => ({ ...a, [q.id]: String(i) }))}
                  data-testid={`option-${i}`}
                  className={`w-full text-left px-4 py-3 rounded-xl border-2 text-sm transition-all ${answers[q.id] === String(i) ? 'border-indigo-500 bg-indigo-50 text-indigo-700 font-medium' : 'border-slate-200 hover:border-slate-300'}`}>
                  <span className="font-semibold mr-2">{String.fromCharCode(65 + i)}.</span>{opt}
                </button>
              ))}
            </div>
          )}
          {q.question_type === 'TRUE_FALSE' && (
            <div className="flex gap-3">
              {['true', 'false'].map(v => (
                <button key={v} onClick={() => setAnswers(a => ({ ...a, [q.id]: v }))} data-testid={`tf-${v}`}
                  className={`flex-1 py-3 rounded-xl border-2 text-sm font-medium ${answers[q.id] === v ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-200 hover:border-slate-300'}`}>
                  {v === 'true' ? '✓ True' : '✕ False'}
                </button>
              ))}
            </div>
          )}
          {(q.question_type === 'FILL_IN_BLANK' || q.question_type === 'SHORT_ANSWER') && (
            <input type="text" value={answers[q.id] || ''} onChange={e => setAnswers(a => ({ ...a, [q.id]: e.target.value }))}
              placeholder="Type your answer…" data-testid="answer-text"
              className="w-full border-2 border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-indigo-400" />
          )}
        </div>
      </div>
      <div className="bg-white border-t px-6 py-4 flex items-center justify-between">
        <button onClick={() => setCurrent(Math.max(0, current - 1))} disabled={current === 0}
          className="inline-flex items-center gap-2 border border-slate-200 rounded-lg px-4 py-2 text-sm disabled:opacity-50"><ChevronLeft className="h-4 w-4" /> Previous</button>
        {current < exam.questions.length - 1 ? (
          <button onClick={() => setCurrent(current + 1)} data-testid="next-question-btn"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-4 py-2 text-sm">Next <ChevronRight className="h-4 w-4" /></button>
        ) : (
          <button onClick={submit} data-testid="submit-exam-btn"
            className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg px-4 py-2 text-sm"><CheckCircle className="h-4 w-4" /> Submit</button>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }: any) {
  return <div className="bg-slate-50 rounded-lg p-4 text-center"><p className="text-2xl font-bold text-slate-900">{value}</p><p className="text-sm text-slate-500">{label}</p></div>
}

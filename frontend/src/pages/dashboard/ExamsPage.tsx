import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { Plus, ClipboardList, Clock, Users, CheckCircle, Eye, Sparkles, X, RefreshCw, RotateCcw, Pencil, BookOpen } from 'lucide-react'
import { toast } from 'sonner'
import { useConfirm } from 'components/ConfirmDialog'

export default function ExamsPage() {
  const { hasRole } = useAuth()
  const qc = useQueryClient()
  const isAdmin = hasRole('ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR')
  const [aiOpen, setAiOpen] = useState(false)
  const [attemptsExam, setAttemptsExam] = useState<any>(null)

  const { data: exams = [], isLoading } = useQuery<any[]>({
    queryKey: ['exams'], queryFn: async () => (await api.get('/exams')).data,
  })

  const createMut = useMutation({
    mutationFn: async () => (await api.post('/exams', {
      title: 'Untitled Exam', passing_score: 70, max_attempts: 3, is_published: false,
    })).data,
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ['exams'] }); toast.success('Exam created'); },
  })

  return (
    <div className="p-8" data-testid="exams-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">Exams</h1>
          <p className="text-slate-500 mt-1">{isLoading ? 'Loading…' : `${exams.length} exams total`}</p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <button onClick={() => setAiOpen(true)} data-testid="ai-quiz-btn"
              className="inline-flex items-center gap-2 text-sm border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-lg font-medium">
              <Sparkles className="h-4 w-4 text-amber-500" /> AI quiz
            </button>
            <button onClick={() => createMut.mutate()} data-testid="new-exam-btn"
              className="inline-flex items-center gap-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium">
              <Plus className="h-4 w-4" /> New Exam
            </button>
          </div>
        )}
      </div>

      {aiOpen && <AIQuizModal onClose={() => setAiOpen(false)} onDone={() => { setAiOpen(false); qc.invalidateQueries({ queryKey: ['exams'] }) }} />}
      {attemptsExam && <AttemptsModal exam={attemptsExam} onClose={() => setAttemptsExam(null)} />}

      {isLoading ? <div className="flex items-center justify-center py-16"><div className="w-7 h-7 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div> :
       exams.length === 0 ? (
        <div className="text-center py-16 text-slate-400">No exams yet.</div>
      ) : (
        <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Exam</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Questions</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Attempts</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Time Limit</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Status</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y">
              {exams.map(e => (
                <tr key={e.id} data-testid={`exam-row-${e.id}`}>
                  <td className="px-6 py-4 font-medium text-slate-900">{e.title}</td>
                  <td className="px-6 py-4"><span className="inline-flex items-center gap-1.5 text-slate-600"><ClipboardList className="h-3.5 w-3.5" /> {e.question_count}</span></td>
                  <td className="px-6 py-4"><span className="inline-flex items-center gap-1.5 text-slate-600"><Users className="h-3.5 w-3.5" /> {e.attempt_count}</span></td>
                  <td className="px-6 py-4">{e.time_limit_minutes ? <span className="inline-flex items-center gap-1.5 text-slate-600"><Clock className="h-3.5 w-3.5" /> {e.time_limit_minutes}m</span> : <span className="text-slate-400">—</span>}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full ${e.is_published ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                      <CheckCircle className="h-3 w-3" /> {e.is_published ? 'Published' : 'Draft'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    {isAdmin && (
                      <button onClick={() => setAttemptsExam(e)} data-testid={`exam-attempts-btn-${e.id}`}
                        className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 mr-4">
                        <Users className="h-3.5 w-3.5" /> Attempts
                      </button>
                    )}
                    <Link to={`/take/${e.id}`} className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700">
                      <Eye className="h-3.5 w-3.5" /> {isAdmin ? 'Preview' : 'Take'}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function AttemptsModal({ exam, onClose }: { exam: any, onClose: () => void }) {
  const qc = useQueryClient()
  const confirm = useConfirm()
  const [tab, setTab] = useState<'learners' | 'insights'>('learners')
  const [editingQ, setEditingQ] = useState<any>(null)
  const { data, isLoading } = useQuery<any>({
    queryKey: ['exam-attempts', exam.id],
    queryFn: async () => (await api.get(`/exams/${exam.id}/attempts`)).data,
  })
  const { data: insights, isLoading: insightsLoading } = useQuery<any>({
    queryKey: ['exam-insights', exam.id],
    queryFn: async () => (await api.get(`/exams/${exam.id}/question-insights`)).data,
    enabled: tab === 'insights',
  })

  const resetMut = useMutation({
    mutationFn: async (userId: number) =>
      (await api.post(`/exams/${exam.id}/attempts/reset`, { user_id: userId })).data,
    onSuccess: (d) => {
      toast.success(`Reset ${d.deleted} attempt${d.deleted !== 1 ? 's' : ''} — the learner can retake the exam`)
      qc.invalidateQueries({ queryKey: ['exam-attempts', exam.id] })
      qc.invalidateQueries({ queryKey: ['exams'] })
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Could not reset attempts'),
  })

  const reset = async (l: any) => {
    if (!(await confirm({
      title: 'Reset exam attempts?',
      description: `${l.name || l.email} has used ${l.attempts_used} of ${data?.max_attempts} attempts. Resetting deletes their attempt history for "${exam.title}" so they can start fresh.`,
      confirmLabel: 'Reset attempts',
    }))) return
    resetMut.mutate(l.user_id)
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" data-testid="attempts-modal">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-slate-900">Attempts · {exam.title}</h2>
            <p className="text-xs text-slate-500 mt-0.5">Max {data?.max_attempts ?? exam.max_attempts ?? '—'} attempts per learner</p>
          </div>
          <button onClick={onClose} data-testid="attempts-modal-close" className="text-slate-400 hover:text-slate-600"><X className="h-5 w-5" /></button>
        </div>
        <div className="px-6 pt-3 border-b flex gap-4">
          {(['learners', 'insights'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              data-testid={`attempts-tab-${t}`}
              className={`pb-2 text-sm font-medium border-b-2 -mb-px ${tab === t ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-400 hover:text-slate-600'}`}>
              {t === 'learners' ? 'Learners' : 'Question insights'}
            </button>
          ))}
        </div>
        {tab === 'insights' ? (
          <div className="flex-1 overflow-y-auto p-6" data-testid="question-insights-panel">
            {insightsLoading ? (
              <div className="flex items-center justify-center py-12"><div className="w-6 h-6 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>
            ) : !insights?.questions?.length ? (
              <p className="text-center text-slate-400 py-12 text-sm">No questions on this exam.</p>
            ) : (
              <>
                <div className="flex items-center justify-between mb-4 gap-4">
                  <p className="text-xs text-slate-500">
                    Based on {insights.total_attempts} attempt{insights.total_attempts !== 1 ? 's' : ''} — sorted by miss rate, most-missed first.
                  </p>
                  {insights.course_id && (
                    <Link to={`/courses/${insights.course_id}/edit`} data-testid="insights-edit-course-link"
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-700 whitespace-nowrap">
                      <BookOpen className="h-3.5 w-3.5" /> Edit course content
                    </Link>
                  )}
                </div>
                <div className="space-y-4">
                  {insights.questions.map((q: any, i: number) => {
                    const rate = q.miss_rate
                    const barColor = rate == null ? 'bg-slate-200' : rate >= 50 ? 'bg-red-500' : rate >= 25 ? 'bg-amber-500' : 'bg-emerald-500'
                    return (
                      <div key={q.question_id} data-testid={`insight-row-${q.question_id}`}>
                        <div className="flex items-start justify-between gap-4 mb-1.5">
                          <p className="text-sm text-slate-800"><span className="text-slate-400 mr-1.5">{i + 1}.</span>{q.question_text}</p>
                          <div className="flex items-center gap-3 whitespace-nowrap">
                            <span className={`text-xs font-semibold ${rate == null ? 'text-slate-400' : rate >= 50 ? 'text-red-600' : rate >= 25 ? 'text-amber-600' : 'text-emerald-600'}`}>
                              {rate == null ? 'No data' : `${rate}% missed`}
                            </span>
                            <button onClick={() => setEditingQ(q)} data-testid={`edit-question-btn-${q.question_id}`}
                              className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700">
                              <Pencil className="h-3 w-3" /> Edit
                            </button>
                          </div>
                        </div>
                        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div className={`h-full ${barColor}`} style={{ width: `${rate ?? 0}%` }} />
                        </div>
                        <p className="text-[11px] text-slate-400 mt-1">{q.correct}/{q.answered} answered correctly · {q.question_type === 'TRUE_FALSE' ? 'True/False' : q.question_type === 'MULTIPLE_CHOICE' ? 'Multiple choice' : 'Short answer'} · {q.points} pt{q.points !== 1 ? 's' : ''}</p>
                      </div>
                    )
                  })}
                </div>
              </>
            )}
          </div>
        ) : (
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12"><div className="w-6 h-6 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>
          ) : !data?.learners?.length ? (
            <p className="text-center text-slate-400 py-12 text-sm">No attempts yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b sticky top-0">
                <tr>
                  <th className="text-left px-6 py-2.5 font-medium text-slate-500">Learner</th>
                  <th className="text-left px-4 py-2.5 font-medium text-slate-500">Used</th>
                  <th className="text-left px-4 py-2.5 font-medium text-slate-500">Best</th>
                  <th className="text-left px-4 py-2.5 font-medium text-slate-500">Status</th>
                  <th />
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.learners.map((l: any) => (
                  <tr key={l.user_id} data-testid={`attempt-row-${l.user_id}`}>
                    <td className="px-6 py-3">
                      <p className="font-medium text-slate-800">{l.name || '—'}</p>
                      <p className="text-xs text-slate-400">{l.email}</p>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{l.attempts_used} / {data.max_attempts}</td>
                    <td className="px-4 py-3 text-slate-600">{l.best_score != null ? `${Math.round(l.best_score)}%` : '—'}</td>
                    <td className="px-4 py-3">
                      {l.passed
                        ? <span className="text-xs font-medium text-emerald-600">Passed</span>
                        : l.attempts_used >= (data.max_attempts || 0)
                          ? <span className="text-xs font-medium text-red-600">Locked out</span>
                          : <span className="text-xs text-slate-400">In progress</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => reset(l)} disabled={resetMut.isPending}
                        data-testid={`reset-attempts-btn-${l.user_id}`}
                        className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700 disabled:opacity-50">
                        <RotateCcw className="h-3.5 w-3.5" /> Reset
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        )}
        {editingQ && (
          <EditQuestionModal examId={exam.id} question={editingQ}
            onClose={() => setEditingQ(null)}
            onSaved={() => {
              setEditingQ(null)
              qc.invalidateQueries({ queryKey: ['exam-insights', exam.id] })
            }} />
        )}
      </div>
    </div>
  )
}

function EditQuestionModal({ examId, question, onClose, onSaved }: {
  examId: number, question: any, onClose: () => void, onSaved: () => void
}) {
  const [text, setText] = useState<string>(question.question_text || '')
  const [options, setOptions] = useState<string[]>(question.options || [])
  const [correct, setCorrect] = useState<string>(question.correct_answer ?? '')
  const [explanation, setExplanation] = useState<string>(question.explanation || '')
  const [points, setPoints] = useState<number>(question.points || 1)

  const saveMut = useMutation({
    mutationFn: async () => {
      const body: any = { question_text: text, correct_answer: correct, explanation, points }
      if (question.question_type === 'MULTIPLE_CHOICE') body.options = options
      return (await api.patch(`/exams/${examId}/questions/${question.question_id}`, body)).data
    },
    onSuccess: () => { toast.success('Question updated'); onSaved() },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Could not save question'),
  })

  return (
    <div className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center p-4" data-testid="edit-question-modal">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[85vh] overflow-y-auto">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <h3 className="font-semibold text-slate-900">Edit question</h3>
          <button onClick={onClose} data-testid="edit-question-close" className="text-slate-400 hover:text-slate-600"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Question</label>
            <textarea value={text} onChange={e => setText(e.target.value)} rows={2}
              data-testid="edit-question-text"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
          {question.question_type === 'MULTIPLE_CHOICE' && (
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Options <span className="text-slate-400">(select the correct one)</span></label>
              <div className="space-y-2">
                {options.map((opt, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input type="radio" name="correct-option" checked={correct === String(i)}
                      onChange={() => setCorrect(String(i))} data-testid={`edit-correct-radio-${i}`}
                      className="accent-indigo-600" />
                    <input value={opt} data-testid={`edit-option-${i}`}
                      onChange={e => setOptions(options.map((o, j) => j === i ? e.target.value : o))}
                      className="flex-1 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  </div>
                ))}
              </div>
            </div>
          )}
          {question.question_type === 'TRUE_FALSE' && (
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Correct answer</label>
              <div className="flex gap-2">
                {['true', 'false'].map(v => (
                  <button key={v} onClick={() => setCorrect(v)} data-testid={`edit-tf-${v}`}
                    aria-pressed={correct === v}
                    className={`px-4 py-1.5 rounded-lg text-sm font-medium border ${correct === v ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                    {v === 'true' ? 'True' : 'False'}
                  </button>
                ))}
              </div>
            </div>
          )}
          {question.question_type === 'SHORT_ANSWER' && (
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Correct answer</label>
              <input value={correct} onChange={e => setCorrect(e.target.value)} data-testid="edit-short-answer"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Points</label>
              <input type="number" min={1} value={points} onChange={e => setPoints(Number(e.target.value) || 1)}
                data-testid="edit-question-points"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Explanation <span className="text-slate-400">(shown after answering)</span></label>
            <textarea value={explanation} onChange={e => setExplanation(e.target.value)} rows={2}
              data-testid="edit-question-explanation"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
        </div>
        <div className="px-6 py-4 border-t flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-lg">Cancel</button>
          <button onClick={() => saveMut.mutate()} disabled={saveMut.isPending || !text.trim()}
            data-testid="edit-question-save"
            className="px-4 py-2 text-sm font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg disabled:opacity-50">
            {saveMut.isPending ? 'Saving…' : 'Save question'}
          </button>
        </div>
      </div>
    </div>
  )
}

function AIQuizModal({ onClose, onDone }: { onClose: () => void, onDone: () => void }) {
  const [courseId, setCourseId] = useState<number | ''>('')
  const [numQ, setNumQ] = useState(5)
  const [qType, setQType] = useState<'MULTIPLE_CHOICE' | 'TRUE_FALSE' | 'SHORT_ANSWER' | 'MIXED'>('MULTIPLE_CHOICE')
  const [examMode, setExamMode] = useState<'new' | 'append'>('new')
  const [targetExamId, setTargetExamId] = useState<number | ''>('')
  const [loading, setLoading] = useState(false)
  const [regenIdx, setRegenIdx] = useState<number | null>(null)
  const [questions, setQuestions] = useState<any[] | null>(null)

  const { data: courses = [] } = useQuery<any[]>({
    queryKey: ['courses-for-ai'], queryFn: async () => (await api.get('/courses')).data,
  })
  const { data: exams = [] } = useQuery<any[]>({
    queryKey: ['exams-for-ai'], queryFn: async () => (await api.get('/exams')).data,
  })

  const generate = async () => {
    if (!courseId) return toast.error('Select a course')
    setLoading(true)
    try {
      const r = await api.post('/exams/ai-generate-questions',
        { course_id: courseId, num_questions: numQ, question_type: qType })
      setQuestions(r.data.questions)
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Generation failed') }
    finally { setLoading(false) }
  }

  const regenerateOne = async (i: number) => {
    if (!questions || !courseId) return
    setRegenIdx(i)
    try {
      const avoid = questions.map(q => q.question_text)
      const r = await api.post('/exams/ai-generate-questions',
        { course_id: courseId, num_questions: 1, question_type: questions[i].question_type, avoid_topics: avoid })
      const fresh = r.data.questions[0]
      if (!fresh) return toast.error('AI returned nothing — try again')
      setQuestions(qs => qs!.map((q, k) => k === i ? fresh : q))
      toast.success('Regenerated')
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Regenerate failed') }
    finally { setRegenIdx(null) }
  }

  const save = async () => {
    if (!questions?.length) return
    setLoading(true)
    try {
      let examId: number
      if (examMode === 'new') {
        const course = courses.find((c: any) => c.id === courseId)
        const r = await api.post('/exams', {
          title: `${course?.title || 'Course'} — Assessment`,
          course_id: courseId, passing_score: 70, max_attempts: 3, is_published: false,
        })
        examId = r.data.id
      } else {
        if (!targetExamId) return toast.error('Pick an exam to append to')
        examId = Number(targetExamId)
      }
      await api.put(`/exams/${examId}/questions?mode=${examMode === 'new' ? 'replace' : 'append'}`,
        questions.map((q, i) => ({
          question_text: q.question_text,
          question_type: q.question_type || 'MULTIPLE_CHOICE',
          options: q.options || [], correct_answer: q.correct_answer,
          explanation: q.explanation, points: 1, order_index: i + 1,
        })))
      toast.success(`${questions.length} questions saved`)
      onDone()
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Save failed') }
    finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div onClick={e => e.stopPropagation()} className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col" data-testid="ai-quiz-modal">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2"><Sparkles className="h-4 w-4 text-amber-500" /> AI Quiz Generator</h2>
            <p className="text-xs text-slate-500 mt-0.5">Turn a course's slide content into multiple-choice questions you can review before saving.</p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded"><X className="h-4 w-4 text-slate-400" /></button>
        </div>

        <div className="p-6 overflow-y-auto flex-1 space-y-4">
          {!questions ? (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wide mb-1.5">Course</label>
                <select value={courseId} onChange={e => setCourseId(Number(e.target.value) || '')} data-testid="ai-course"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white">
                  <option value="">Pick a course…</option>
                  {courses.map((c: any) => <option key={c.id} value={c.id}>{c.title}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wide mb-1.5">Number of questions</label>
                <input type="number" min={1} max={20} value={numQ} onChange={e => setNumQ(Number(e.target.value))}
                  data-testid="ai-numq" className="w-32 px-3 py-2 border border-slate-200 rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wide mb-1.5">Question type</label>
                <select value={qType} onChange={e => setQType(e.target.value as any)} data-testid="ai-type"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white">
                  <option value="MULTIPLE_CHOICE">Multiple choice (4 options)</option>
                  <option value="TRUE_FALSE">True / False</option>
                  <option value="SHORT_ANSWER">Short answer</option>
                  <option value="MIXED">Mixed (auto-pick per question)</option>
                </select>
              </div>
              <button onClick={generate} disabled={loading || !courseId} data-testid="ai-generate-btn"
                className="inline-flex items-center gap-2 bg-amber-500 hover:bg-amber-600 disabled:bg-slate-300 text-white text-sm font-medium px-4 py-2 rounded-lg">
                {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                {loading ? 'Generating…' : 'Generate questions'}
              </button>
            </>
          ) : (
            <>
              <div className="text-xs text-slate-500">Review {questions.length} generated questions. Edit, remove, or save them to a new or existing exam.</div>
              {questions.map((q, i) => (
                <div key={i} className="border border-slate-200 rounded-lg p-3 bg-slate-50/50" data-testid={`ai-q-${i}`}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium text-sm text-slate-900 flex-1">{i + 1}. {q.question_text}
                      <span className="ml-2 text-[10px] uppercase tracking-wide font-semibold text-slate-400">{(q.question_type || 'MCQ').replace('_', ' ')}</span>
                    </p>
                    <button onClick={() => regenerateOne(i)} disabled={regenIdx === i}
                      data-testid={`ai-regen-${i}`}
                      className="text-[11px] text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50 px-1.5 py-0.5 rounded inline-flex items-center gap-1 disabled:opacity-40">
                      <RefreshCw className={`h-3 w-3 ${regenIdx === i ? 'animate-spin' : ''}`} /> Regenerate
                    </button>
                  </div>
                  {q.question_type === 'SHORT_ANSWER' ? (
                    <p className="mt-2 text-xs text-emerald-700 font-medium">Expected: {q.correct_answer}</p>
                  ) : (
                    <ul className="mt-2 space-y-1 text-xs">
                      {(q.options || []).map((o: string, j: number) => (
                        <li key={j} className={o === q.correct_answer ? 'text-emerald-700 font-medium' : 'text-slate-500'}>
                          {o === q.correct_answer ? '✓ ' : '  '}{o}
                        </li>
                      ))}
                    </ul>
                  )}
                  {q.explanation && <p className="text-[11px] text-slate-500 mt-2 italic">{q.explanation}</p>}
                  <button onClick={() => setQuestions(qs => qs!.filter((_, k) => k !== i))}
                          className="text-[11px] text-red-500 hover:text-red-700 mt-1">Remove</button>
                </div>
              ))}
              <div className="border-t pt-4 space-y-3">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wide">Save to</label>
                <div className="flex gap-3 items-center">
                  <label className="text-xs"><input type="radio" checked={examMode === 'new'} onChange={() => setExamMode('new')} className="mr-1" data-testid="ai-mode-new" /> Create new exam</label>
                  <label className="text-xs"><input type="radio" checked={examMode === 'append'} onChange={() => setExamMode('append')} className="mr-1" data-testid="ai-mode-append" /> Append to existing exam</label>
                </div>
                {examMode === 'append' && (
                  <select value={targetExamId} onChange={e => setTargetExamId(Number(e.target.value) || '')}
                    data-testid="ai-target-exam"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white">
                    <option value="">Pick an exam…</option>
                    {exams.map((e: any) => <option key={e.id} value={e.id}>{e.title} ({e.question_count} Qs)</option>)}
                  </select>
                )}
              </div>
            </>
          )}
        </div>

        {questions && (
          <div className="px-6 py-4 border-t flex justify-end gap-2 bg-slate-50">
            <button onClick={() => setQuestions(null)} className="px-4 py-2 text-sm text-slate-600 rounded-lg hover:bg-slate-100">Generate more</button>
            <button onClick={save} disabled={loading || !questions.length} data-testid="ai-save-btn"
              className="inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-xl text-sm font-medium">
              {loading ? 'Saving…' : `Save ${questions.length} question${questions.length !== 1 ? 's' : ''}`}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}


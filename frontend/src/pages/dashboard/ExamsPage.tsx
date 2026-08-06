import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { Plus, ClipboardList, Clock, Users, CheckCircle, Eye, Sparkles, X, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

export default function ExamsPage() {
  const { hasRole } = useAuth()
  const qc = useQueryClient()
  const isAdmin = hasRole('ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR')
  const [aiOpen, setAiOpen] = useState(false)

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


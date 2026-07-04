import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { Plus, Search, BookOpen, Clock, Users, Sparkles, Eye, Edit, LogIn, X, Loader2, Copy, ArrowUpDown, GripVertical } from 'lucide-react'
import { toast } from 'sonner'
import { SortableList } from 'components/SortableList'
import { LearningStreakBadge } from 'components/LearningStreakBadge'
import { StreakLeaderboardTrigger } from 'components/StreakLeaderboardModal'

export default function CoursesPage() {
  const qc = useQueryClient()
  const { hasRole } = useAuth()
  const isAdmin = hasRole('ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR')
  const [search, setSearch] = useState('')
  const [showAI, setShowAI] = useState(false)
  const [reordering, setReordering] = useState(false)

  const { data: courses = [], isLoading } = useQuery<any[]>({
    queryKey: ['courses'], queryFn: async () => (await api.get('/courses')).data,
  })

  const reorderMut = useMutation({
    mutationFn: async (ids: number[]) => (await api.patch('/courses/reorder', { course_ids: ids })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['courses'] }),
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Reorder failed'),
  })

  const createMut = useMutation({
    mutationFn: async (body: any) => (await api.post('/courses', body)).data,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['courses'] }); toast.success('Course created') },
  })

  const dupMut = useMutation({
    mutationFn: async (id: number) => (await api.post(`/courses/${id}/duplicate`)).data,
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['courses'] })
      toast.success(`Duplicated with ${d.slides_copied} slide${d.slides_copied !== 1 ? 's' : ''}`)
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Could not duplicate'),
  })

  const handleNewCourse = async () => {
    const c = await createMut.mutateAsync({ title: 'Untitled Course', status: 'DRAFT' })
    window.location.href = `/courses/${c.id}/edit`
  }

  const filtered = courses.filter(c => !search || c.title.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="p-8" data-testid="courses-page">
      {showAI && <AIBuilderModal onClose={() => setShowAI(false)} onApplied={() => {
        qc.invalidateQueries({ queryKey: ['courses'] }); setShowAI(false)
      }} />}

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">{isAdmin ? 'Courses' : 'My Courses'}</h1>
          <div className="flex items-center gap-3 mt-1">
            <p className="text-slate-500">{isLoading ? 'Loading…' : `${courses.length} courses available`}</p>
            {!isAdmin && <LearningStreakBadge />}
            {!isAdmin && <StreakLeaderboardTrigger />}
          </div>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <button onClick={() => setReordering(r => !r)} data-testid="reorder-toggle"
              className={`inline-flex items-center gap-2 text-sm border px-4 py-2 rounded-lg font-medium ${reordering ? 'bg-amber-500 hover:bg-amber-600 text-white border-amber-500' : 'border-slate-200 hover:bg-slate-50 text-slate-700'}`}>
              <ArrowUpDown className="h-4 w-4" /> {reordering ? 'Done' : 'Reorder'}
            </button>
            <button onClick={() => setShowAI(true)} data-testid="ai-builder-btn"
              className="inline-flex items-center gap-2 text-sm border border-indigo-200 text-indigo-700 hover:bg-indigo-50 px-4 py-2 rounded-lg font-medium">
              <Sparkles className="h-4 w-4" /> AI Builder
            </button>
            <button onClick={handleNewCourse} disabled={createMut.isPending} data-testid="new-course-btn"
              className="inline-flex items-center gap-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium">
              <Plus className="h-4 w-4" /> New Course
            </button>
          </div>
        )}
      </div>

      <div className="relative mb-6 max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search courses..." data-testid="courses-search"
          className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
      </div>

      {isLoading ? <Spinner /> : filtered.length === 0 ? (
        <div className="text-center py-16">
          <BookOpen className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-500">{search ? 'No matches' : isAdmin ? 'No courses yet. Create one!' : 'No courses available yet.'}</p>
        </div>
      ) : reordering ? (
        <div className="max-w-2xl space-y-2" data-testid="reorder-list">
          <p className="text-xs text-slate-500 mb-3">Drag to set catalog order. The order applies to both the admin list and the public portal.</p>
          <SortableList items={filtered} onReorder={(ids) => reorderMut.mutate(ids as number[])}>
            {(c: any, listeners: any) => (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm flex items-center gap-3 p-3 mb-2" data-testid={`reorder-row-${c.id}`}>
                <button {...listeners} className="text-slate-400 hover:text-slate-600 cursor-grab" aria-label="drag"><GripVertical className="h-5 w-5" /></button>
                <div className={`w-10 h-10 rounded-lg ${c.cover_color} flex-shrink-0`} />
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-900 truncate">{c.title}</p>
                  <p className="text-xs text-slate-500">{c.category || 'Uncategorised'} · {c.status}</p>
                </div>
                <span className="text-xs text-slate-400 font-mono">#{c.id}</span>
              </div>
            )}
          </SortableList>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(c => (
            <div key={c.id} className="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-shadow" data-testid={`course-card-${c.id}`}>
              <div className={`h-32 ${c.cover_color} flex items-end p-4 relative overflow-hidden`}>
                {isAdmin && c.mindmap_thumbnail_svg && (
                  <>
                    <img
                      alt="Mind map preview"
                      src={`data:image/svg+xml;base64,${c.mindmap_thumbnail_svg}`}
                      className="absolute inset-0 w-full h-full object-cover pointer-events-none"
                      data-testid={`mindmap-thumb-${c.id}`}
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent pointer-events-none" />
                    <span className="absolute top-2 right-2 z-10 text-[9px] font-semibold px-1.5 py-0.5 rounded bg-white/90 text-slate-700 shadow-sm uppercase tracking-wide">
                      Mind map
                    </span>
                  </>
                )}
                <span className={`relative z-10 text-[10px] font-medium px-2 py-0.5 rounded-full ${c.status === 'PUBLISHED' ? 'bg-white/20 text-white' : 'bg-black/20 text-white/80'}`}>
                  {c.status}
                </span>
              </div>
              <div className="p-4">
                <h3 className="font-semibold text-slate-900 truncate">{c.title}</h3>
                {c.category && <p className="text-xs text-slate-400 mt-0.5">{c.category}</p>}
                <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                  <span className="flex items-center gap-1"><BookOpen className="h-3.5 w-3.5" /> {c.slide_count} slides</span>
                  <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {c.enrollment_count}</span>
                  {c.duration_minutes && <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {c.duration_minutes}m</span>}
                </div>
                <div className="flex gap-2 mt-4">
                  {isAdmin ? (
                    <>
                      <Link to={`/courses/${c.id}/edit`} className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs border border-slate-200 hover:border-slate-300 rounded-lg py-1.5 font-medium">
                        <Edit className="h-3.5 w-3.5" /> Edit
                      </Link>
                      <button onClick={() => dupMut.mutate(c.id)} disabled={dupMut.isPending} data-testid={`duplicate-${c.id}`}
                        title="Duplicate as draft"
                        className="inline-flex items-center justify-center text-xs border border-slate-200 hover:border-slate-300 rounded-lg px-2.5 py-1.5 font-medium disabled:opacity-50">
                        <Copy className="h-3.5 w-3.5" />
                      </button>
                      <Link to={`/learn/${c.id}`} className="inline-flex items-center justify-center gap-1.5 text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-3 py-1.5 font-medium">
                        <Eye className="h-3.5 w-3.5" /> Preview
                      </Link>
                    </>
                  ) : (
                    <Link to={`/learn/${c.id}`} className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg py-1.5 font-medium">
                      <LogIn className="h-3.5 w-3.5" /> Start Course
                    </Link>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Spinner() {
  return <div className="flex items-center justify-center py-16">
    <div className="w-7 h-7 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
  </div>
}

function AIBuilderModal({ onClose, onApplied }: { onClose: () => void; onApplied: () => void }) {
  const [topic, setTopic] = useState('')
  const [description, setDescription] = useState('')
  const [numSlides, setNumSlides] = useState(5)
  const [includeQuiz, setIncludeQuiz] = useState(true)
  const [numQuestions, setNumQuestions] = useState(5)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const generate = async () => {
    if (!topic.trim()) { setError('Topic is required'); return }
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await api.post('/ai/course-builder', {
        topic, description, num_slides: numSlides,
        include_quiz: includeQuiz, num_questions: numQuestions,
      })
      setResult(r.data)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Generation failed')
    } finally { setLoading(false) }
  }

  const apply = async () => {
    setLoading(true)
    try {
      const courseRes = await api.post('/courses', {
        title: topic || 'AI Generated Course',
        description: 'Generated by AI — edit to customise.',
        status: 'DRAFT',
      })
      const courseId = courseRes.data.id
      for (const s of result.slides) {
        await api.post(`/courses/${courseId}/slides`, s)
      }
      if (result.questions?.length) {
        const examRes = await api.post('/exams', {
          title: `${topic} — Assessment`, course_id: courseId,
          passing_score: 70, max_attempts: 3, is_published: false,
        })
        await api.put(`/exams/${examRes.data.id}/questions`, result.questions)
      }
      toast.success('Course generated and saved as draft')
      onApplied()
      window.location.href = `/courses/${courseId}/edit`
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to apply')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="ai-builder-modal">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b bg-gradient-to-r from-indigo-50 to-violet-50">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">AI Course Builder</h2>
              <p className="text-[11px] text-slate-500">Generate slides & quiz from a topic</p>
            </div>
          </div>
          <button onClick={onClose}><X className="h-5 w-5 text-slate-400" /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {!result ? (<>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Topic *</label>
              <input value={topic} onChange={e => setTopic(e.target.value)} data-testid="ai-topic"
                placeholder="e.g. Introduction to Music Copyright Law"
                className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Additional context</label>
              <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} data-testid="ai-context"
                className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5"># Slides</label>
                <input type="number" min={1} max={20} value={numSlides} onChange={e => setNumSlides(+e.target.value || 5)}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Quiz</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={includeQuiz} onChange={e => setIncludeQuiz(e.target.checked)} /><span className="text-sm">Include quiz</span></label>
                {includeQuiz && <input type="number" min={1} max={20} value={numQuestions} onChange={e => setNumQuestions(+e.target.value || 5)}
                  className="w-full mt-2 border border-slate-200 rounded-xl px-3 py-2 text-sm" />}
              </div>
            </div>
            {error && <div className="bg-red-50 border border-red-100 rounded-xl p-3 text-sm text-red-600">{error}</div>}
          </>) : (
            <div className="space-y-3">
              <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4">
                <p className="text-sm font-semibold text-emerald-800">Generated successfully!</p>
                <p className="text-xs text-emerald-600 mt-0.5">{result.slides.length} slides{result.questions?.length ? ` + ${result.questions.length} questions` : ''}</p>
              </div>
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {result.slides.map((s: any, i: number) => (
                  <div key={i} className="bg-slate-50 rounded-lg p-3">
                    <p className="text-sm font-medium text-slate-800">{s.order_index}. {s.title}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="px-6 py-4 border-t flex justify-end gap-3 bg-slate-50">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 rounded-lg">Cancel</button>
          {result ? (
            <button onClick={apply} disabled={loading} data-testid="ai-apply"
              className="inline-flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium disabled:opacity-50">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Apply to Course'}
            </button>
          ) : (
            <button onClick={generate} disabled={loading || !topic.trim()} data-testid="ai-generate"
              className="inline-flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium disabled:opacity-50">
              {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</> : <><Sparkles className="h-4 w-4" /> Generate</>}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

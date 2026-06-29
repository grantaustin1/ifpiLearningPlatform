import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from 'lib/api'
import { ArrowLeft, Save, Plus, Trash2, Eye, CheckCircle2, Send, EyeOff, GripVertical, Lock, X, History, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'
import { SortableList } from 'components/SortableList'

const SLIDE_TYPES = ['TEXT', 'VIDEO', 'AUDIO', 'IMAGE', 'PDF', 'SCORM']

export default function CourseEditPage() {
  const { id } = useParams()
  const [course, setCourse] = useState<any>(null)
  const [slides, setSlides] = useState<any[]>([])
  const [active, setActive] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<Date | null>(null)
  const [prereqs, setPrereqs] = useState<any[]>([])
  const [allCourses, setAllCourses] = useState<any[]>([])
  const [showAddPrereq, setShowAddPrereq] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  const load = async () => {
    const [r, p, all] = await Promise.all([
      api.get(`/courses/${id}`),
      api.get(`/courses/${id}/prerequisites`),
      api.get('/courses'),
    ])
    setCourse(r.data)
    setSlides(r.data.slides || [])
    setActive(r.data.slides?.[0]?.id ?? null)
    setPrereqs(p.data)
    setAllCourses(all.data)
  }
  useEffect(() => { load() }, [id])

  const save = async () => {
    if (!course) return
    setSaving(true)
    try {
      await api.patch(`/courses/${id}`, {
        title: course.title, description: course.description,
        category: course.category, duration_minutes: course.duration_minutes,
        price_cents: course.price_cents, passing_score: course.passing_score,
        status: course.status,
      })
      for (const s of slides.filter(x => !x._local)) {
        await api.patch(`/courses/${id}/slides/${s.id}`, {
          title: s.title, content: s.content, slide_type: s.slide_type,
          media_url: s.media_url, order_index: s.order_index, is_required: s.is_required,
        })
      }
      for (const s of slides.filter(x => x._local)) {
        const created = await api.post(`/courses/${id}/slides`, {
          title: s.title, content: s.content, slide_type: s.slide_type,
          media_url: s.media_url, is_required: true,
        })
        setSlides(prev => prev.map(x => x.id === s.id ? created.data : x))
      }
      setSavedAt(new Date()); toast.success('Saved')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Save failed')
    } finally { setSaving(false) }
  }

  const addSlide = () => {
    const s = { id: -Date.now(), title: `Slide ${slides.length + 1}`, slide_type: 'TEXT', content: '', media_url: '', order_index: slides.length + 1, is_required: true, _local: true }
    setSlides([...slides, s]); setActive(s.id)
  }

  const removeSlide = async (sid: number) => {
    const s = slides.find(x => x.id === sid)
    if (!s) return
    if (!s._local) await api.delete(`/courses/${id}/slides/${sid}`).catch(() => {})
    const remaining = slides.filter(x => x.id !== sid)
    setSlides(remaining)
    if (active === sid) setActive(remaining[0]?.id ?? null)
  }

  const publish = async () => {
    try {
      const r = await api.post(`/courses/${id}/publish`)
      setCourse({ ...course, status: r.data.status })
      toast.success('Course published')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Publish failed')
    }
  }

  const unpublish = async () => {
    try {
      const r = await api.post(`/courses/${id}/unpublish`)
      setCourse({ ...course, status: r.data.status })
      toast.success('Course unpublished')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed')
    }
  }

  const update = (sid: number, patch: any) =>
    setSlides(prev => prev.map(s => s.id === sid ? { ...s, ...patch } : s))

  if (!course) return <div className="flex items-center justify-center h-screen"><div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>

  const activeSlide = slides.find(s => s.id === active)

  return (
    <div className="flex h-screen bg-slate-50" data-testid="course-edit-page">
      <aside className="w-64 bg-white border-r flex flex-col">
        <div className="p-4 border-b">
          <Link to="/courses" className="flex items-center gap-2 text-sm text-slate-500 mb-3"><ArrowLeft className="h-4 w-4" /> All courses</Link>
          <input value={course.title || ''} onChange={e => setCourse({ ...course, title: e.target.value })} data-testid="edit-course-title"
            className="w-full text-sm font-semibold border-b border-transparent focus:border-indigo-300 focus:outline-none bg-transparent" />
          <p className="text-xs text-slate-400 mt-1">{slides.length} slides</p>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          <SortableList
            items={slides}
            onReorder={async (ids) => {
              setSlides(prev => ids.map((id, i) => ({ ...prev.find((p: any) => p.id === id), order_index: i + 1 })))
              const persisted = slides.filter((s: any) => !s._local).map((s: any) => s.id)
              const orderedIds = ids.filter((id: any) => persisted.includes(id))
              if (orderedIds.length) {
                try { await api.patch(`/courses/${id}/slides/reorder`, { slide_ids: orderedIds }) }
                catch { toast.error('Could not save new order') }
              }
            }}
          >
            {(s: any, listeners) => (
              <div onClick={() => setActive(s.id)} data-testid={`slide-row-${s.id}`}
                className={`flex items-center gap-2 px-2 py-2.5 rounded-lg mb-0.5 group ${s.id === active ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-slate-50 text-slate-600'}`}>
                <span {...listeners} className="cursor-grab active:cursor-grabbing p-0.5 text-slate-300 hover:text-slate-500" title="Drag to reorder">
                  <GripVertical className="h-3.5 w-3.5" />
                </span>
                <span className="text-xs flex-1 truncate cursor-pointer">{(slides.findIndex((x: any) => x.id === s.id)) + 1}. {s.title || 'Untitled'}</span>
                {s._local && <span className="text-[10px] text-amber-500 font-medium">unsaved</span>}
                <button onClick={e => { e.stopPropagation(); removeSlide(s.id) }} className="opacity-0 group-hover:opacity-100"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            )}
          </SortableList>
        </div>
        <div className="p-3 border-t">
          <button onClick={addSlide} data-testid="add-slide-btn"
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 border-2 border-dashed border-slate-200 rounded-lg text-xs text-slate-400 hover:border-indigo-300 hover:text-indigo-600">
            <Plus className="h-3.5 w-3.5" /> Add Slide
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col">
        <div className="bg-white border-b px-5 py-3 flex items-center justify-between">
          {savedAt ? <div className="text-sm text-emerald-600 flex items-center gap-2"><CheckCircle2 className="h-4 w-4" /> Saved {savedAt.toLocaleTimeString()}</div> : <div />}
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${course.status === 'PUBLISHED' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`} data-testid="course-status-pill">{course.status}</span>
            <Link to={`/learn/${id}`} className="inline-flex items-center gap-1.5 text-xs border border-slate-200 rounded-lg px-3 py-1.5 font-medium"><Eye className="h-3.5 w-3.5" /> Preview</Link>
            <button onClick={save} disabled={saving} data-testid="save-course-btn"
              className="inline-flex items-center gap-1.5 text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg px-3 py-1.5 font-medium disabled:opacity-50">
              <Save className="h-3.5 w-3.5" /> {saving ? 'Saving…' : 'Save'}
            </button>
            {course.status === 'PUBLISHED' ? (
              <button onClick={unpublish} data-testid="unpublish-btn"
                className="inline-flex items-center gap-1.5 text-xs border border-amber-300 text-amber-700 hover:bg-amber-50 rounded-lg px-3 py-1.5 font-medium">
                <EyeOff className="h-3.5 w-3.5" /> Unpublish
              </button>
            ) : (
              <button onClick={publish} data-testid="publish-btn"
                className="inline-flex items-center gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg px-3 py-1.5 font-medium shadow-sm">
                <Send className="h-3.5 w-3.5" /> Publish
              </button>
            )}
          </div>
        </div>
        {activeSlide ? (
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-3xl mx-auto space-y-4">
              <input value={activeSlide.title || ''} onChange={e => update(activeSlide.id, { title: e.target.value })}
                placeholder="Slide title" data-testid="slide-title"
                className="w-full text-xl font-semibold border-b border-slate-200 focus:border-indigo-400 focus:outline-none pb-1 bg-transparent" />
              <div className="flex gap-2 flex-wrap items-center">
                {SLIDE_TYPES.map(t => (
                  <button key={t} onClick={() => update(activeSlide.id, { slide_type: t })}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium ${activeSlide.slide_type === t ? 'bg-indigo-100 text-indigo-700 ring-2 ring-indigo-400' : 'bg-slate-100 text-slate-500'}`}>{t}</button>
                ))}
                {!activeSlide._local && (
                  <button onClick={() => setShowHistory(true)} data-testid="slide-history-btn"
                    className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600 hover:bg-slate-200">
                    <History className="h-3 w-3" /> History
                  </button>
                )}
              </div>
              <textarea value={activeSlide.content || ''} onChange={e => update(activeSlide.id, { content: e.target.value })}
                rows={14} data-testid="slide-content"
                placeholder={activeSlide.slide_type === 'TEXT' ? 'HTML content (e.g. <h2>Title</h2><p>Body…</p>)' : 'Description text'}
                className="w-full border border-slate-200 rounded-xl p-4 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-400" />
              {activeSlide.slide_type !== 'TEXT' && (
                <input value={activeSlide.media_url || ''} onChange={e => update(activeSlide.id, { media_url: e.target.value })}
                  placeholder="Media URL (video, audio, image, PDF)"
                  className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm" />
              )}
            </div>
          </div>
        ) : <div className="flex-1 flex items-center justify-center text-slate-400">Select or add a slide to start</div>}
      </div>

      <aside className="w-72 bg-white border-l p-4 overflow-y-auto">
        <h3 className="font-semibold text-slate-900 text-sm mb-4">Course Settings</h3>
        <Field label="Title"><input value={course.title || ''} onChange={e => setCourse({ ...course, title: e.target.value })} data-testid="sidebar-course-title" className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" /></Field>
        <Field label="Description"><textarea value={course.description || ''} onChange={e => setCourse({ ...course, description: e.target.value })} rows={3} className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" /></Field>
        <Field label="Category"><input value={course.category || ''} onChange={e => setCourse({ ...course, category: e.target.value })} className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" /></Field>
        <Field label="Duration (minutes)"><input type="number" min={0} value={course.duration_minutes || 0} onChange={e => setCourse({ ...course, duration_minutes: +e.target.value })} className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" /></Field>
        <Field label="Passing score (%)"><input type="number" min={0} max={100} value={course.passing_score} onChange={e => setCourse({ ...course, passing_score: +e.target.value })} className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" /></Field>
        <Field label="Price (cents)"><input type="number" min={0} value={course.price_cents || 0} onChange={e => setCourse({ ...course, price_cents: +e.target.value })} className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" /></Field>
        <Field label="Status">
          <select value={course.status} onChange={e => setCourse({ ...course, status: e.target.value })} className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm">
            <option value="DRAFT">DRAFT</option><option value="PUBLISHED">PUBLISHED</option><option value="ARCHIVED">ARCHIVED</option>
          </select>
        </Field>

        <div className="mt-6 pt-4 border-t border-slate-200" data-testid="prereqs-section">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wide flex items-center gap-1.5"><Lock className="h-3.5 w-3.5" /> Prerequisites</h4>
            <button onClick={() => setShowAddPrereq(true)} data-testid="add-prereq-btn"
              className="text-xs text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1"><Plus className="h-3 w-3" /> Add</button>
          </div>
          {prereqs.length === 0 ? (
            <p className="text-xs text-slate-400">No prerequisites — learners can enrol directly.</p>
          ) : (
            <div className="space-y-1.5">
              {prereqs.map((p: any) => (
                <div key={p.id} className="flex items-center gap-2 px-2 py-1.5 bg-slate-50 rounded-lg group" data-testid={`prereq-${p.course_id}`}>
                  <Lock className="h-3 w-3 text-slate-400 flex-shrink-0" />
                  <span className="text-xs text-slate-700 flex-1 truncate">{p.title}</span>
                  <button onClick={async () => {
                    await api.delete(`/courses/${id}/prerequisites/${p.course_id}`)
                    setPrereqs(prereqs.filter((x: any) => x.id !== p.id))
                    toast.success('Prerequisite removed')
                  }} data-testid={`remove-prereq-${p.course_id}`}
                    className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-500">
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      {showAddPrereq && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" data-testid="add-prereq-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">Add a prerequisite</h3>
              <button onClick={() => setShowAddPrereq(false)}><X className="h-5 w-5 text-slate-400" /></button>
            </div>
            <div className="p-6 max-h-80 overflow-y-auto space-y-2">
              <p className="text-xs text-slate-500 mb-3">Learners must complete the selected course before they can enrol in <strong>{course.title}</strong>.</p>
              {allCourses.filter((c: any) => c.id !== Number(id) && !prereqs.some((p: any) => p.course_id === c.id)).map((c: any) => (
                <button key={c.id} onClick={async () => {
                  await api.post(`/courses/${id}/prerequisites/${c.id}`)
                  await load()
                  setShowAddPrereq(false)
                  toast.success('Prerequisite added')
                }} data-testid={`pick-prereq-${c.id}`}
                  className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 text-left">
                  <div className={`w-8 h-8 rounded-lg ${c.cover_color}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{c.title}</p>
                    <p className="text-[11px] text-slate-400">{c.status}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {showHistory && activeSlide && (
        <SlideHistoryModal
          courseId={Number(id)} slideId={activeSlide.id}
          onClose={() => setShowHistory(false)}
          onRestored={async () => { setShowHistory(false); await load(); toast.success('Slide restored') }}
        />
      )}
    </div>
  )
}

function SlideHistoryModal({ courseId, slideId, onClose, onRestored }:
  { courseId: number; slideId: number; onClose: () => void; onRestored: () => void }) {
  const [versions, setVersions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [restoring, setRestoring] = useState<number | null>(null)

  useEffect(() => {
    api.get(`/courses/${courseId}/slides/${slideId}/versions`)
      .then(r => setVersions(r.data.items))
      .finally(() => setLoading(false))
  }, [courseId, slideId])

  const restore = async (n: number) => {
    if (!window.confirm(`Restore this slide to version ${n}? Your current content will be saved as a new version first, so nothing is lost.`)) return
    setRestoring(n)
    try {
      await api.post(`/courses/${courseId}/slides/${slideId}/versions/${n}/restore`)
      onRestored()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Restore failed')
    } finally { setRestoring(null) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose} data-testid="slide-history-modal">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-3 border-b flex items-center justify-between">
          <h3 className="font-semibold text-slate-900 flex items-center gap-2"><History className="h-4 w-4 text-indigo-600" /> Slide version history</h3>
          <button onClick={onClose}><X className="h-5 w-5 text-slate-400" /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : versions.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-6">No previous versions yet — versions are created automatically every time you save a change.</p>
          ) : (
            <ul className="space-y-2" data-testid="version-list">
              {versions.map(v => (
                <li key={v.id} className="border border-slate-200 rounded-xl p-3 flex items-start gap-3"
                    data-testid={`version-row-${v.version_number}`}>
                  <div className="text-xs font-mono font-bold text-slate-400 w-8 mt-0.5">v{v.version_number}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-800 truncate">{v.title || '(untitled)'}</p>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      {v.slide_type || '—'} · {v.change_summary || 'edit'}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {v.created_at ? new Date(v.created_at).toLocaleString() : ''}
                    </p>
                  </div>
                  <button onClick={() => restore(v.version_number)} disabled={restoring === v.version_number}
                    data-testid={`restore-v${v.version_number}`}
                    className="inline-flex items-center gap-1 text-xs border border-indigo-200 text-indigo-700 hover:bg-indigo-50 px-2.5 py-1 rounded-lg disabled:opacity-50">
                    <RotateCcw className="h-3 w-3" /> {restoring === v.version_number ? 'Restoring…' : 'Restore'}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: any) {
  return <div className="mb-4"><label className="block text-xs font-medium text-slate-500 mb-1">{label}</label>{children}</div>
}

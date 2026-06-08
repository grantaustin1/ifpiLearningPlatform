import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from 'lib/api'
import { ArrowLeft, Save, Plus, Trash2, Eye, CheckCircle2 } from 'lucide-react'
import { toast } from 'sonner'

const SLIDE_TYPES = ['TEXT', 'VIDEO', 'AUDIO', 'IMAGE', 'PDF']

export default function CourseEditPage() {
  const { id } = useParams()
  const [course, setCourse] = useState<any>(null)
  const [slides, setSlides] = useState<any[]>([])
  const [active, setActive] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<Date | null>(null)

  const load = async () => {
    const r = await api.get(`/courses/${id}`)
    setCourse(r.data)
    setSlides(r.data.slides || [])
    setActive(r.data.slides?.[0]?.id ?? null)
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
          {slides.map((s, i) => (
            <div key={s.id} onClick={() => setActive(s.id)} data-testid={`slide-row-${i}`}
              className={`flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer mb-0.5 group ${s.id === active ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-slate-50 text-slate-600'}`}>
              <span className="text-xs flex-1 truncate">{i + 1}. {s.title || 'Untitled'}</span>
              {s._local && <span className="text-[10px] text-amber-500 font-medium">unsaved</span>}
              <button onClick={e => { e.stopPropagation(); removeSlide(s.id) }} className="opacity-0 group-hover:opacity-100"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          ))}
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
          <div className="flex gap-2">
            <Link to={`/learn/${id}`} className="inline-flex items-center gap-1.5 text-xs border border-slate-200 rounded-lg px-3 py-1.5 font-medium"><Eye className="h-3.5 w-3.5" /> Preview</Link>
            <button onClick={save} disabled={saving} data-testid="save-course-btn"
              className="inline-flex items-center gap-1.5 text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-3 py-1.5 font-medium disabled:opacity-50">
              <Save className="h-3.5 w-3.5" /> {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
        {activeSlide ? (
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-3xl mx-auto space-y-4">
              <input value={activeSlide.title || ''} onChange={e => update(activeSlide.id, { title: e.target.value })}
                placeholder="Slide title" data-testid="slide-title"
                className="w-full text-xl font-semibold border-b border-slate-200 focus:border-indigo-400 focus:outline-none pb-1 bg-transparent" />
              <div className="flex gap-2 flex-wrap">
                {SLIDE_TYPES.map(t => (
                  <button key={t} onClick={() => update(activeSlide.id, { slide_type: t })}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium ${activeSlide.slide_type === t ? 'bg-indigo-100 text-indigo-700 ring-2 ring-indigo-400' : 'bg-slate-100 text-slate-500'}`}>{t}</button>
                ))}
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
      </aside>
    </div>
  )
}

function Field({ label, children }: any) {
  return <div className="mb-4"><label className="block text-xs font-medium text-slate-500 mb-1">{label}</label>{children}</div>
}

import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from 'lib/api'
import { ArrowLeft, Save, Send, EyeOff, Trash2, Plus, X, Layers, BookOpen } from 'lucide-react'
import { toast } from 'sonner'

export default function LearningPathEditPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const [path, setPath] = useState<any>(null)
  const [allCourses, setAllCourses] = useState<any[]>([])
  const [adding, setAdding] = useState(false)
  const [chosenCourse, setChosenCourse] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    const [p, c] = await Promise.all([
      api.get(`/learning-paths/${id}`),
      api.get('/courses'),
    ])
    setPath(p.data)
    setAllCourses(c.data)
  }

  useEffect(() => { load() }, [id])

  const save = async () => {
    setSaving(true)
    try {
      await api.patch(`/learning-paths/${id}`, {
        title: path.title, description: path.description,
        cover_color: path.cover_color, estimated_hours: path.estimated_hours,
        price_cents: path.price_cents,
      })
      toast.success('Saved')
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Save failed') }
    finally { setSaving(false) }
  }

  const publish = async () => {
    try {
      await api.post(`/learning-paths/${id}/publish`)
      toast.success('Learning path published')
      load()
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Publish failed') }
  }

  const unpublish = async () => {
    await api.patch(`/learning-paths/${id}`, { status: 'DRAFT' })
    toast.success('Unpublished')
    load()
  }

  const addCourse = async () => {
    if (!chosenCourse) return
    try {
      await api.post(`/learning-paths/${id}/items`, { course_id: chosenCourse })
      setAdding(false); setChosenCourse(null)
      load()
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Could not add course') }
  }

  const removeCourse = async (courseId: number) => {
    await api.delete(`/learning-paths/${id}/items/${courseId}`)
    load()
  }

  const deletePath = async () => {
    if (!confirm('Delete this learning path? This cannot be undone.')) return
    await api.delete(`/learning-paths/${id}`)
    toast.success('Deleted')
    nav('/learning-paths')
  }

  if (!path) return <div className="flex items-center justify-center h-screen"><div className="w-8 h-8 border-4 border-violet-600 border-t-transparent rounded-full animate-spin" /></div>

  const inPath = new Set(path.items.map((i: any) => i.course_id))
  const availableCourses = allCourses.filter((c: any) => !inPath.has(c.id))

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col" data-testid="path-edit-page">
      <div className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <Link to="/learning-paths" className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700">
          <ArrowLeft className="h-4 w-4" /> All paths
        </Link>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${path.status === 'PUBLISHED' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`} data-testid="path-status-pill">{path.status}</span>
          <button onClick={save} disabled={saving} data-testid="save-path-btn"
            className="inline-flex items-center gap-1.5 text-xs bg-slate-100 hover:bg-slate-200 rounded-lg px-3 py-1.5 font-medium disabled:opacity-50">
            <Save className="h-3.5 w-3.5" /> {saving ? 'Saving…' : 'Save'}
          </button>
          {path.status === 'PUBLISHED' ? (
            <button onClick={unpublish} className="inline-flex items-center gap-1.5 text-xs border border-amber-300 text-amber-700 hover:bg-amber-50 rounded-lg px-3 py-1.5 font-medium">
              <EyeOff className="h-3.5 w-3.5" /> Unpublish
            </button>
          ) : (
            <button onClick={publish} data-testid="publish-path-btn"
              className="inline-flex items-center gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg px-3 py-1.5 font-medium shadow-sm">
              <Send className="h-3.5 w-3.5" /> Publish
            </button>
          )}
          <button onClick={deletePath} className="inline-flex items-center gap-1.5 text-xs text-red-600 hover:bg-red-50 rounded-lg px-3 py-1.5 font-medium">
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </button>
        </div>
      </div>

      <div className="flex-1 grid lg:grid-cols-3 gap-6 p-6 max-w-6xl mx-auto w-full">
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-2xl shadow-sm p-6">
            <input value={path.title} onChange={e => setPath({ ...path, title: e.target.value })}
              className="w-full text-2xl font-bold border-b border-transparent focus:border-violet-300 focus:outline-none pb-1 bg-transparent" data-testid="path-title-input" />
            <textarea value={path.description || ''} onChange={e => setPath({ ...path, description: e.target.value })}
              placeholder="Describe what learners will gain from this path…" rows={3}
              className="w-full mt-3 text-sm border border-slate-200 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-violet-400" />
          </div>

          <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h2 className="font-semibold text-slate-900 flex items-center gap-2"><Layers className="h-4 w-4 text-violet-600" /> Courses in this path</h2>
              <button onClick={() => setAdding(true)} disabled={availableCourses.length === 0} data-testid="add-course-to-path-btn"
                className="inline-flex items-center gap-1.5 text-xs bg-violet-100 hover:bg-violet-200 text-violet-700 rounded-lg px-3 py-1.5 font-medium disabled:opacity-50">
                <Plus className="h-3.5 w-3.5" /> Add Course
              </button>
            </div>
            {path.items.length === 0 ? (
              <p className="px-6 py-10 text-center text-slate-400 text-sm">No courses yet. Add the first course to get started.</p>
            ) : (
              <ol className="divide-y">
                {path.items.map((it: any, i: number) => (
                  <li key={it.id} className="flex items-center gap-4 px-6 py-4" data-testid={`path-item-${i}`}>
                    <span className="w-7 h-7 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center text-xs font-bold">{i + 1}</span>
                    <BookOpen className="h-4 w-4 text-slate-400" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-slate-900">{it.course_title}</p>
                      <p className="text-[11px] text-slate-400">{it.course_status} · {it.is_required ? 'Required' : 'Optional'}</p>
                    </div>
                    <button onClick={() => removeCourse(it.course_id)} className="text-slate-300 hover:text-red-500" data-testid={`remove-item-${i}`}>
                      <X className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>

        <aside className="bg-white rounded-2xl shadow-sm p-5 h-fit">
          <h3 className="font-semibold text-slate-900 text-sm mb-4">Path Settings</h3>
          <Field label="Estimated hours">
            <input type="number" min={0} value={path.estimated_hours || 0} onChange={e => setPath({ ...path, estimated_hours: +e.target.value || null })}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          </Field>
          <Field label="Price (cents)">
            <input type="number" min={0} value={path.price_cents || 0} onChange={e => setPath({ ...path, price_cents: +e.target.value })}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          </Field>
          <Field label="Cover colour">
            <select value={path.cover_color} onChange={e => setPath({ ...path, cover_color: e.target.value })}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm">
              {['bg-violet-500', 'bg-indigo-500', 'bg-blue-500', 'bg-emerald-500', 'bg-amber-500', 'bg-pink-500', 'bg-slate-700'].map(c => <option key={c} value={c}>{c.replace('bg-', '').replace('-500', '').replace('-700', '')}</option>)}
            </select>
          </Field>
        </aside>
      </div>

      {adding && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" data-testid="add-course-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <h3 className="font-semibold">Add a course to this path</h3>
              <button onClick={() => setAdding(false)}><X className="h-5 w-5 text-slate-400" /></button>
            </div>
            <div className="p-6 max-h-80 overflow-y-auto space-y-2">
              {availableCourses.map((c: any) => (
                <label key={c.id} className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer border-2 ${chosenCourse === c.id ? 'border-violet-500 bg-violet-50' : 'border-transparent hover:bg-slate-50'}`}>
                  <input type="radio" checked={chosenCourse === c.id} onChange={() => setChosenCourse(c.id)} className="sr-only" />
                  <div className={`w-8 h-8 rounded-lg ${c.cover_color}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{c.title}</p>
                    <p className="text-[11px] text-slate-400">{c.status}</p>
                  </div>
                </label>
              ))}
            </div>
            <div className="px-6 py-4 border-t flex justify-end gap-2 bg-slate-50">
              <button onClick={() => setAdding(false)} className="px-4 py-2 text-sm text-slate-600">Cancel</button>
              <button onClick={addCourse} disabled={!chosenCourse} data-testid="confirm-add-course"
                className="px-4 py-2 text-sm bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-medium disabled:opacity-50">Add</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Field({ label, children }: any) {
  return <div className="mb-4"><label className="block text-xs font-medium text-slate-500 mb-1">{label}</label>{children}</div>
}

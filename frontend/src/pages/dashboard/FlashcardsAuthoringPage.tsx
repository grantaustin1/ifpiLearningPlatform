import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from 'lib/api'
import { Sparkles, Loader2, Plus, Trash2, Save, ArrowLeft, Wand2 } from 'lucide-react'
import { toast } from 'sonner'

interface Card {
  id?: number
  front: string
  back: string
  hint?: string | null
  difficulty: number
  tags: string[]
  slide_id?: number | null
  source_chunk_ids?: number[]
  _preview?: boolean
}

interface Course { id: number; title: string }

export default function FlashcardsAuthoringPage() {
  const { courseId } = useParams()
  const nav = useNavigate()
  const cid = Number(courseId)
  const [course, setCourse] = useState<Course | null>(null)
  const [existing, setExisting] = useState<Card[]>([])
  const [preview, setPreview] = useState<Card[]>([])
  const [count, setCount] = useState(6)
  const [useSources, setUseSources] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    try {
      const c = await api.get(`/courses/${cid}`)
      setCourse({ id: c.data.id, title: c.data.title })
    } catch { /* fallback */ }
    try {
      const r = await api.get(`/authoring/flashcards/by-course/${cid}`)
      setExisting(r.data.items)
    } catch { setExisting([]) }
  }
  useEffect(() => { load() /* eslint-disable-next-line */ }, [cid])

  const generate = async () => {
    setGenerating(true)
    try {
      const r = await api.post('/authoring/flashcards/generate', {
        course_id: cid, count, use_sources: useSources,
      })
      const cards: Card[] = (r.data.cards || []).map((c: any) => ({ ...c, _preview: true }))
      setPreview(cards)
      if (cards.length === 0) toast.warning('No cards returned')
      else toast.success(`Generated ${cards.length} cards — review + save below`)
    } catch (e: any) {
      toast.error(String(e?.response?.data?.detail ?? 'Generation failed'))
    } finally { setGenerating(false) }
  }

  const updatePreview = (i: number, patch: Partial<Card>) => {
    setPreview(p => p.map((c, idx) => (idx === i ? { ...c, ...patch } : c)))
  }
  const removePreview = (i: number) => setPreview(p => p.filter((_, idx) => idx !== i))

  const saveAll = async () => {
    if (preview.length === 0) return
    setSaving(true)
    try {
      await api.post('/authoring/flashcards/bulk-save', {
        course_id: cid,
        cards: preview.map(c => ({
          front: c.front, back: c.back, hint: c.hint || null,
          difficulty: c.difficulty, tags: c.tags || [],
          slide_id: c.slide_id ?? null,
          source_chunk_ids: c.source_chunk_ids ?? [],
        })),
      })
      toast.success(`Saved ${preview.length} flashcards`)
      setPreview([])
      load()
    } catch (e: any) {
      toast.error(String(e?.response?.data?.detail ?? 'Save failed'))
    } finally { setSaving(false) }
  }

  const deleteExisting = async (id: number) => {
    if (!window.confirm('Delete this flashcard?')) return
    await api.delete(`/authoring/flashcards/${id}`)
    load()
  }

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <button onClick={() => nav(`/courses/${cid}/edit`)} className="text-xs text-indigo-600 hover:underline inline-flex items-center gap-1" data-testid="fc-back-btn">
        <ArrowLeft className="h-3 w-3" /> Back to course editor
      </button>
      <div>
        <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
          <Sparkles className="text-indigo-500" /> Flashcards — {course?.title || `Course #${cid}`}
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          Generate spaced-repetition ready cards from your course material. Learners see them in
          {' '}<span className="font-mono">/learn/{cid}/flashcards</span>.
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4" data-testid="fc-generate-form">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">How many cards?</label>
            <input type="number" min={1} max={40} value={count}
              onChange={(e) => setCount(Math.max(1, Math.min(40, Number(e.target.value) || 6)))}
              className="w-24 border border-slate-300 rounded-lg px-3 py-2 text-sm"
              data-testid="fc-count-input" />
          </div>
          <label className="inline-flex items-center gap-2 text-xs text-slate-600">
            <input type="checkbox" checked={useSources} onChange={(e) => setUseSources(e.target.checked)}
              data-testid="fc-use-sources" />
            Augment with source library
          </label>
          <button onClick={generate} disabled={generating}
            data-testid="fc-generate-btn"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white px-5 py-2 rounded-lg text-sm font-semibold shadow-md shadow-indigo-500/20">
            {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
            {generating ? 'Generating…' : 'Generate flashcards'}
          </button>
        </div>
      </div>

      {preview.length > 0 && (
        <div className="bg-white rounded-2xl border-2 border-indigo-200 shadow-sm p-6 space-y-4" data-testid="fc-preview-panel">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-800">Preview ({preview.length})</h2>
            <button onClick={saveAll} disabled={saving}
              data-testid="fc-save-btn"
              className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white px-5 py-2 rounded-lg text-sm font-semibold">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save all
            </button>
          </div>
          <div className="grid gap-3">
            {preview.map((c, i) => (
              <div key={i} className="border border-slate-200 rounded-xl p-4 space-y-2" data-testid={`fc-preview-card-${i}`}>
                <div className="flex gap-3">
                  <div className="flex-1 space-y-2">
                    <textarea value={c.front} onChange={(e) => updatePreview(i, { front: e.target.value })}
                      rows={2}
                      placeholder="Front (question)"
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-medium" />
                    <textarea value={c.back} onChange={(e) => updatePreview(i, { back: e.target.value })}
                      rows={3}
                      placeholder="Back (answer)"
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700" />
                    <div className="flex items-center gap-3">
                      <label className="text-[11px] text-slate-500 flex items-center gap-1">
                        Difficulty
                        <select value={c.difficulty} onChange={(e) => updatePreview(i, { difficulty: Number(e.target.value) })}
                          className="border border-slate-200 rounded px-2 py-1 text-xs bg-white">
                          {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}</option>)}
                        </select>
                      </label>
                      <span className="text-[11px] text-slate-500 truncate">
                        Tags: {(c.tags || []).join(', ') || '—'}
                      </span>
                    </div>
                  </div>
                  <button onClick={() => removePreview(i)}
                    className="text-rose-500 hover:text-rose-700 p-2 h-fit"
                    data-testid={`fc-remove-preview-${i}`}>
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-3" data-testid="fc-existing-panel">
        <h2 className="text-lg font-semibold text-slate-800">
          Saved flashcards ({existing.length})
        </h2>
        {existing.length === 0 ? (
          <p className="text-sm text-slate-500">Nothing yet — generate some above.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {existing.map(c => (
              <li key={c.id} className="py-3 flex items-start gap-3" data-testid={`fc-existing-${c.id}`}>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{c.front}</p>
                  <p className="text-xs text-slate-500 truncate mt-0.5">{c.back}</p>
                  <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-400">
                    Difficulty {c.difficulty} · {c.tags?.join(', ') || 'no tags'}
                  </div>
                </div>
                <button onClick={() => deleteExisting(c.id!)}
                  className="text-rose-500 hover:text-rose-700"
                  data-testid={`fc-delete-${c.id}`}>
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

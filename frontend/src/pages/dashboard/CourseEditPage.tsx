import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from 'lib/api'
import { API_URL } from 'lib/env'
import { ArrowLeft, Save, Plus, Trash2, Eye, CheckCircle2, Send, EyeOff, GripVertical, Lock, X, History, RotateCcw, Sparkles, Upload, LayoutTemplate } from 'lucide-react'
import { toast } from 'sonner'
import { SortableList } from 'components/SortableList'
import { RichTextEditor } from 'components/RichTextEditor'
import { SlideTemplatePicker, SlideTemplate } from 'components/SlideTemplates'
import { useConfirm } from 'components/ConfirmDialog'
import { CourseFunnelPanel } from './CourseFunnelPanel'
import { CourseReviewsPanel } from './CourseReviewsPanel'

const SLIDE_TYPES = ['TEXT', 'VIDEO', 'AUDIO', 'IMAGE', 'PDF', 'SCORM']

export default function CourseEditPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const [searchParams] = useSearchParams()
  const [course, setCourse] = useState<any>(null)
  const [slides, setSlides] = useState<any[]>([])
  const [active, setActive] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [uploadingCover, setUploadingCover] = useState(false)
  const [uploadingSlideImg, setUploadingSlideImg] = useState(false)
  const [showGallery, setShowGallery] = useState(false)
  const [gallery, setGallery] = useState<any[]>([])
  const coverInputRef = useRef<HTMLInputElement>(null)
  const slideImgInputRef = useRef<HTMLInputElement>(null)

  const openGallery = async () => {
    setShowGallery(true)
    if (gallery.length === 0) {
      try { setGallery((await api.get('/uploads/cover-library')).data) }
      catch { toast.error('Could not load the photo gallery') }
    }
  }
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
    const wanted = Number(searchParams.get('slide'))
    const found = wanted && r.data.slides?.some((s: any) => s.id === wanted)
    setActive(found ? wanted : (r.data.slides?.[0]?.id ?? null))
    if (found) setTimeout(() => document.querySelector(`[data-testid="slide-row-${wanted}"]`)?.scrollIntoView({ block: 'center' }), 300)
    setPrereqs(p.data)
    setAllCourses(all.data)
  }
  useEffect(() => { load() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    if (!course) return
    setSaving(true)
    try {
      await api.patch(`/courses/${id}`, {
        title: course.title, description: course.description,
        category: course.category, duration_minutes: course.duration_minutes,
        price_cents: course.price_cents, passing_score: course.passing_score,
        status: course.status, cover_image: course.cover_image || null,
      })
      for (const s of slides.filter(x => !x._local)) {
        await api.patch(`/courses/${id}/slides/${s.id}`, {
          title: s.title, content: s.content, slide_type: s.slide_type,
          media_url: s.media_url, order_index: s.order_index, is_required: s.is_required,
          image_position: s.image_position || 'above',
          media_opacity: s.media_opacity ?? 100,
        })
      }
      for (const s of slides.filter(x => x._local)) {
        const created = await api.post(`/courses/${id}/slides`, {
          title: s.title, content: s.content, slide_type: s.slide_type,
          media_url: s.media_url, is_required: true,
          image_position: s.image_position || 'above',
          media_opacity: s.media_opacity ?? 100,
        })
        setSlides(prev => prev.map(x => x.id === s.id ? created.data : x))
      }
      setSavedAt(new Date())
      if (searchParams.get('slide')) {
        toast.success('Saved — taking you back to the slide')
        const backSlide = active && active > 0 ? `?slide=${active}` : ''
        nav(`/learn/${id}${backSlide}`)
      } else {
        toast.success('Saved')
      }
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Save failed')
    } finally { setSaving(false) }
  }

  const addSlide = () => {
    const s = { id: -Date.now(), title: `Slide ${slides.length + 1}`, slide_type: 'TEXT', content: '', media_url: '', order_index: slides.length + 1, is_required: true, _local: true }
    setSlides([...slides, s]); setActive(s.id)
  }

  const [showTemplates, setShowTemplates] = useState(false)

  const addFromTemplate = (t: SlideTemplate) => {
    const s = {
      id: -Date.now(), title: t.name, slide_type: t.slide_type, content: t.content,
      media_url: '', order_index: slides.length + 1, is_required: true,
      image_position: t.image_position || 'above', _local: true,
    }
    setSlides([...slides, s]); setActive(s.id); setShowTemplates(false)
    toast.success(`"${t.name}" slide added — make it yours`)
  }

  const [bulkUploading, setBulkUploading] = useState(false)
  const bulkPhotoRef = useRef<HTMLInputElement>(null)

  const addPhotoSlides = async (files: FileList | null) => {
    if (!files || !files.length) return
    const list = Array.from(files).filter(f => f.type.startsWith('image/'))
    if (!list.length) { toast.error('Please choose image files'); return }
    const oversize = list.find(f => f.size > 5 * 1024 * 1024)
    if (oversize) { toast.error(`"${oversize.name}" is over 5MB — please shrink it first`); return }
    setBulkUploading(true)
    let added = 0
    try {
      for (const f of list) {
        const fd = new FormData()
        fd.append('file', f)
        const r = await api.post('/uploads/image', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
        const title = f.name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').trim() || `Photo ${added + 1}`
        const s = {
          id: -Date.now() - added, title, slide_type: 'IMAGE', content: '',
          media_url: r.data.url, image_position: 'above',
          order_index: slides.length + added + 1, is_required: true, _local: true,
        }
        setSlides(prev => [...prev, s])
        added += 1
      }
      toast.success(`${added} photo slide${added === 1 ? '' : 's'} added — remember to Save`)
    } catch (e: any) {
      toast.error(e?.response?.data?.error?.message || e?.response?.data?.detail || `Upload failed after ${added} photo${added === 1 ? '' : 's'}`)
    } finally {
      setBulkUploading(false)
      if (bulkPhotoRef.current) bulkPhotoRef.current.value = ''
    }
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
          <button onClick={() => setShowTemplates(true)} data-testid="add-template-slide-btn"
            title="Start from a ready-made layout"
            className="w-full mt-2 flex items-center justify-center gap-1.5 px-3 py-2 border-2 border-dashed border-slate-200 rounded-lg text-xs text-slate-400 hover:border-indigo-300 hover:text-indigo-600">
            <LayoutTemplate className="h-3.5 w-3.5" /> From Template
          </button>
          <button onClick={() => bulkPhotoRef.current?.click()} disabled={bulkUploading} data-testid="add-photo-slides-btn"
            title="Pick several photos — each becomes its own slide"
            className="w-full mt-2 flex items-center justify-center gap-1.5 px-3 py-2 border-2 border-dashed border-slate-200 rounded-lg text-xs text-slate-400 hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-50">
            <Upload className="h-3.5 w-3.5" /> {bulkUploading ? 'Uploading photos…' : 'Add Photo Slides'}
          </button>
          <input ref={bulkPhotoRef} type="file" accept="image/*" multiple className="hidden"
            data-testid="add-photo-slides-input"
            onChange={e => addPhotoSlides(e.target.files)} />
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
            <button onClick={() => nav(`/courses/${course.id}/flashcards`)} data-testid="flashcards-btn"
              className="inline-flex items-center gap-1.5 text-xs border border-indigo-300 text-indigo-700 hover:bg-indigo-50 rounded-lg px-3 py-1.5 font-medium">
              <Sparkles className="h-3.5 w-3.5" /> Flashcards
            </button>
            <button onClick={() => nav(`/courses/${course.id}/mindmap`)} data-testid="mindmap-btn"
              className="inline-flex items-center gap-1.5 text-xs border border-pink-300 text-pink-700 hover:bg-pink-50 rounded-lg px-3 py-1.5 font-medium">
              <Sparkles className="h-3.5 w-3.5" /> Mind map
            </button>
            <a
              href={`${API_URL}/api/authoring/pptx/${course.id}`}
              onClick={(e) => {
                e.preventDefault()
                api.get(`/authoring/pptx/${course.id}`, { responseType: 'blob' }).then(r => {
                  const url = URL.createObjectURL(r.data)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `${course.title || 'course'}.pptx`
                  a.click()
                  URL.revokeObjectURL(url)
                }).catch(() => toast.error('PPTX export failed'))
              }}
              data-testid="pptx-download-btn"
              className="inline-flex items-center gap-1.5 text-xs border border-emerald-300 text-emerald-700 hover:bg-emerald-50 rounded-lg px-3 py-1.5 font-medium cursor-pointer">
              <Send className="h-3.5 w-3.5" /> PPTX
            </a>
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
              <RichTextEditor key={activeSlide.id} value={activeSlide.content || ''}
                onChange={html => update(activeSlide.id, { content: html })} />
              {activeSlide.slide_type !== 'TEXT' && (
                <div className="flex gap-2">
                  <input value={activeSlide.media_url || ''} onChange={e => update(activeSlide.id, { media_url: e.target.value })}
                    placeholder="Media URL (video, audio, image, PDF)" data-testid="slide-media-url"
                    className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm" />
                  {activeSlide.slide_type === 'IMAGE' && (
                    <>
                      <button onClick={() => slideImgInputRef.current?.click()} disabled={uploadingSlideImg}
                        data-testid="slide-image-upload-btn" title="Upload a picture from your computer (max 5MB)"
                        className="inline-flex items-center gap-1.5 text-sm border border-slate-200 hover:border-slate-300 rounded-xl px-4 py-2.5 font-medium disabled:opacity-50">
                        <Upload className="h-4 w-4" /> {uploadingSlideImg ? 'Uploading…' : 'Upload'}
                      </button>
                      <input ref={slideImgInputRef} type="file" accept="image/*" className="hidden"
                        data-testid="slide-image-upload-input"
                        onChange={async e => {
                          const f = e.target.files?.[0]
                          if (!f) return
                          if (f.size > 5 * 1024 * 1024) { toast.error('Image too large (max 5MB)'); e.target.value = ''; return }
                          setUploadingSlideImg(true)
                          try {
                            const fd = new FormData()
                            fd.append('file', f)
                            const r = await api.post('/uploads/image', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
                            update(activeSlide.id, { media_url: r.data.url })
                            toast.success('Picture uploaded — remember to Save')
                          } catch (err: any) { toast.error(err?.response?.data?.error?.message || err?.response?.data?.detail || 'Upload failed') }
                          finally { setUploadingSlideImg(false); e.target.value = '' }
                        }} />
                    </>
                  )}
                </div>
              )}
              {['IMAGE', 'VIDEO'].includes(activeSlide.slide_type) && activeSlide.media_url && (
                <div className="flex items-center gap-3" data-testid="media-opacity-control">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">Media transparency:</span>
                  <input type="range" min={20} max={100} step={5}
                    value={activeSlide.media_opacity ?? 100}
                    onChange={e => update(activeSlide.id, { media_opacity: Number(e.target.value) })}
                    data-testid="media-opacity-slider"
                    className="flex-1 accent-indigo-600" />
                  <span className="text-xs font-medium text-slate-600 w-12 text-right" data-testid="media-opacity-value">
                    {activeSlide.media_opacity ?? 100}%
                  </span>
                </div>
              )}
              {activeSlide.slide_type === 'IMAGE' && activeSlide.media_url && (
                <>
                  <img src={activeSlide.media_url} alt="Slide preview" data-testid="slide-image-preview"
                    style={{ opacity: (activeSlide.media_opacity ?? 100) / 100 }}
                    className="max-h-48 rounded-xl border border-slate-200 object-contain" />
                  <div className="flex items-center gap-2" data-testid="image-position-picker">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Picture position:</span>
                    {[['above', 'Above text'], ['beside', 'Beside text'], ['behind', 'Behind text']].map(([val, label]) => (
                      <button key={val} onClick={() => update(activeSlide.id, { image_position: val })}
                        data-testid={`image-position-${val}`}
                        className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${(activeSlide.image_position || 'above') === val ? 'bg-indigo-100 text-indigo-700 ring-2 ring-indigo-400' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}>
                        {label}
                      </button>
                    ))}
                  </div>
                </>
              )}
              <NarrationEditor slide={activeSlide} onUpdated={load} />
              <VisualEditor slide={activeSlide} onUpdated={load} />
              <VideoEditor slide={activeSlide} onUpdated={load} />
            </div>
          </div>
        ) : <div className="flex-1 flex items-center justify-center text-slate-400">Select or add a slide to start</div>}
      </div>

      <aside className="w-80 xl:w-[36rem] bg-white border-l p-4 overflow-y-auto">
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
        <Field label="Cover image">
          <div className="space-y-2">
            {course.cover_image && (
              <div className="relative h-20 rounded-lg overflow-hidden border border-slate-200">
                <img src={course.cover_image} alt="Cover" className="w-full h-full object-cover" data-testid="cover-image-preview" />
                <button onClick={() => setCourse({ ...course, cover_image: '' })} title="Remove cover image"
                  data-testid="cover-image-remove"
                  className="absolute top-1 right-1 p-1 rounded-full bg-black/50 text-white hover:bg-black/70">
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}
            <div className="flex gap-2">
              <input value={course.cover_image || ''} onChange={e => setCourse({ ...course, cover_image: e.target.value })}
                placeholder="Image URL or upload →" data-testid="cover-image-url"
                className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-xs" />
              <button onClick={openGallery} data-testid="cover-gallery-btn" title="Choose from the curated photo gallery"
                className="inline-flex items-center gap-1 text-xs border border-slate-200 hover:border-slate-300 rounded-lg px-2.5 py-1.5 font-medium">
                <Sparkles className="h-3.5 w-3.5" /> Gallery
              </button>
              <button onClick={() => coverInputRef.current?.click()} disabled={uploadingCover}
                data-testid="cover-image-upload-btn" title="Upload an image (max 5MB)"
                className="inline-flex items-center gap-1 text-xs border border-slate-200 hover:border-slate-300 rounded-lg px-2.5 py-1.5 font-medium disabled:opacity-50">
                <Upload className="h-3.5 w-3.5" /> {uploadingCover ? '…' : 'Upload'}
              </button>
              <input ref={coverInputRef} type="file" accept="image/*" className="hidden" onChange={async e => {
                const f = e.target.files?.[0]
                if (!f) return
                setUploadingCover(true)
                try {
                  const fd = new FormData()
                  fd.append('file', f)
                  const r = await api.post('/uploads/image', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
                  setCourse((c: any) => ({ ...c, cover_image: r.data.url }))
                  toast.success('Cover uploaded — remember to Save')
                } catch (err: any) { toast.error(err?.response?.data?.detail || 'Upload failed') }
                finally { setUploadingCover(false); e.target.value = '' }
              }} />
            </div>
          </div>
        </Field>

        <div className="mt-6 pt-4 border-t border-slate-200" data-testid="prereqs-section">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wide flex items-center gap-1.5"><Lock className="h-3.5 w-3.5" /> Prerequisites</h4>
            <button onClick={() => setShowAddPrereq(true)} data-testid="add-prereq-btn"
              className="text-xs text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1"><Plus className="h-3 w-3" /> Add</button>
          </div>          {prereqs.length === 0 ? (
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

        {course?.id && (
          <div className="mt-6 pt-4 border-t border-slate-200">
            <CourseFunnelPanel courseId={course.id} />
          </div>
        )}

        {course?.id && <CourseReviewsPanel courseId={course.id} />}
      </aside>

      {showTemplates && <SlideTemplatePicker onPick={addFromTemplate} onClose={() => setShowTemplates(false)} />}
      {showGallery && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" data-testid="cover-gallery-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">Choose a cover photo</h3>
              <button onClick={() => setShowGallery(false)} data-testid="cover-gallery-close"><X className="h-5 w-5 text-slate-400" /></button>
            </div>
            <div className="p-6 max-h-[28rem] overflow-y-auto">
              {gallery.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-8">Loading gallery…</p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {gallery.map((g: any) => (
                    <button key={g.url} onClick={() => { setCourse({ ...course, cover_image: g.url }); setShowGallery(false); toast.success('Cover selected — remember to Save') }}
                      data-testid={`gallery-photo-${g.label.toLowerCase().replace(/\s+/g, '-')}`}
                      className={`relative h-24 rounded-xl overflow-hidden border-2 group transition-all ${course.cover_image === g.url ? 'border-indigo-500 ring-2 ring-indigo-200' : 'border-transparent hover:border-indigo-300'}`}>
                      <img src={g.url} alt={g.label} loading="lazy" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                      <span className="absolute bottom-0 inset-x-0 text-[10px] font-medium text-white bg-gradient-to-t from-black/70 to-transparent px-2 pt-4 pb-1 text-left">{g.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

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
  const confirm = useConfirm()
  const [versions, setVersions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [restoring, setRestoring] = useState<number | null>(null)

  useEffect(() => {
    api.get(`/courses/${courseId}/slides/${slideId}/versions`)
      .then(r => setVersions(r.data.items))
      .finally(() => setLoading(false))
  }, [courseId, slideId])

  const restore = async (n: number) => {
    if (!(await confirm({
      title: `Restore to version ${n}?`,
      description: 'Your current content will be saved as a new version first, so nothing is lost.',
      confirmLabel: 'Restore',
    }))) return
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

// ── Narration editor (Iter 26a + 30 multi-lang) ─────────────────────
const NARRATION_VOICES = ['alloy', 'ash', 'coral', 'echo', 'fable', 'nova', 'onyx', 'sage', 'shimmer']
const NARRATION_LANGS = [
  ['en', 'English'], ['es', 'Spanish'], ['fr', 'French'], ['de', 'German'],
  ['it', 'Italian'], ['pt', 'Portuguese'], ['nl', 'Dutch'], ['ja', 'Japanese'],
  ['ko', 'Korean'], ['zh', 'Chinese'], ['hi', 'Hindi'],
] as const

function NarrationEditor({ slide, onUpdated }: { slide: any; onUpdated: () => void }) {
  const confirm = useConfirm()
  const [voice, setVoice] = useState(slide.narration_voice || 'nova')
  const [model, setModel] = useState<'tts-1' | 'tts-1-hd'>('tts-1')
  const [language, setLanguage] = useState<string>('en')
  const [translateFirst, setTranslateFirst] = useState(false)
  const [busy, setBusy] = useState(false)

  const gen = async () => {
    setBusy(true)
    try {
      const r = await api.post('/authoring/narration/generate', {
        slide_id: slide.id, voice, model,
        language, translate_first: translateFirst,
      })
      toast.success(`Narration ready · ${r.data.chunk_count} chunk(s) · ${(r.data.size_bytes / 1024).toFixed(1)} KB`)
      onUpdated()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Narration failed')
    } finally { setBusy(false) }
  }

  const clear = async () => {
    if (!(await confirm({
      title: 'Remove narration?',
      description: 'You can regenerate anytime — no data is lost permanently.',
      confirmLabel: 'Remove',
      variant: 'danger',
    }))) return
    await api.delete(`/authoring/narration/${slide.id}`)
    toast.success('Narration cleared')
    onUpdated()
  }

  return (
    <div className="mt-3 rounded-xl border border-indigo-100 bg-indigo-50/40 p-3 space-y-2" data-testid="narration-editor">
      <div className="flex items-center gap-2 text-xs font-semibold text-indigo-800">
        🔊 AI narration <span className="text-slate-500 font-normal">(OpenAI TTS)</span>
      </div>
      {slide.narration_url ? (
        <div className="flex items-center gap-3">
          <audio src={slide.narration_url} controls className="h-9 flex-1" data-testid="narration-audio" />
          <button onClick={clear} className="text-xs text-rose-600 hover:underline" data-testid="narration-clear-btn">
            Remove
          </button>
        </div>
      ) : (
        <p className="text-xs text-slate-500">No narration yet. Pick a voice + language, hit generate.</p>
      )}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <select value={voice} onChange={e => setVoice(e.target.value)}
          className="text-xs border border-slate-200 bg-white rounded px-2 py-1"
          data-testid="narration-voice-select">
          {NARRATION_VOICES.map(v => <option key={v} value={v}>{v}</option>)}
        </select>
        <select value={model} onChange={e => setModel(e.target.value as any)}
          className="text-xs border border-slate-200 bg-white rounded px-2 py-1"
          data-testid="narration-model-select">
          <option value="tts-1">tts-1 (fast)</option>
          <option value="tts-1-hd">tts-1-hd (higher quality)</option>
        </select>
        <select value={language} onChange={e => setLanguage(e.target.value)}
          className="text-xs border border-slate-200 bg-white rounded px-2 py-1"
          data-testid="narration-language-select">
          {NARRATION_LANGS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
        </select>
        {language !== 'en' && (
          <label className="text-[11px] text-slate-600 inline-flex items-center gap-1" title="Translate the slide text to the target language before generating audio">
            <input type="checkbox" checked={translateFirst} onChange={e => setTranslateFirst(e.target.checked)}
              data-testid="narration-translate-first" />
            translate first
          </label>
        )}
        <button onClick={gen} disabled={busy}
          data-testid="narration-generate-btn"
          className="text-xs bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white rounded-lg px-3 py-1.5 font-semibold">
          {busy ? 'Generating…' : slide.narration_url ? 'Re-generate' : 'Generate narration'}
        </button>
      </div>
    </div>
  )
}

// ── Visuals editor (Iter 27a) — Nano Banana infographic ─────────────
function VisualEditor({ slide, onUpdated }: { slide: any; onUpdated: () => void }) {
  const [prompt, setPrompt] = useState('')
  const [busy, setBusy] = useState(false)

  const gen = async () => {
    if (prompt.trim().length < 8) return toast.error('Describe the visual in at least 8 characters')
    setBusy(true)
    try {
      const r = await api.post('/authoring/visuals/generate', {
        prompt: prompt.trim(), slide_id: slide.id, attach_to_slide: true,
      })
      toast.success(`Image generated · ${(r.data.size_bytes / 1024).toFixed(0)} KB`)
      setPrompt('')
      setBusy(false)
      await onUpdated()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Image generation failed')
      setBusy(false)
    }
  }

  const isImage = slide.slide_type === 'IMAGE' && slide.media_url
  return (
    <div className="mt-3 rounded-xl border border-pink-100 bg-pink-50/40 p-3 space-y-2" data-testid="visual-editor">
      <div className="flex items-center gap-2 text-xs font-semibold text-pink-800">
        🎨 AI infographic <span className="text-slate-500 font-normal">(Nano Banana)</span>
      </div>
      {isImage && (
        <img src={slide.media_url} alt="Slide visual" className="rounded-lg max-h-40 object-contain bg-white border border-pink-100" data-testid="visual-preview" />
      )}
      <textarea rows={2} value={prompt} onChange={e => setPrompt(e.target.value)}
        placeholder="Describe the diagram or infographic to generate…"
        className="w-full text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-pink-400"
        data-testid="visual-prompt-input" />
      <button onClick={gen} disabled={busy}
        data-testid="visual-generate-btn"
        className="text-xs bg-pink-600 hover:bg-pink-700 disabled:bg-slate-300 text-white rounded-lg px-3 py-1.5 font-semibold">
        {busy ? 'Generating…' : isImage ? 'Re-generate visual' : 'Generate visual'}
      </button>
    </div>
  )
}

// ── Video editor (Iter 26b) — Sora 2 async with spend preview (Iter 28) ─
function VideoEditor({ slide, onUpdated }: { slide: any; onUpdated: () => void }) {
  const [prompt, setPrompt] = useState('')
  const [model, setModel] = useState<'sora-2' | 'sora-2-pro'>('sora-2')
  const [duration, setDuration] = useState<4 | 8 | 12>(4)
  const [size, setSize] = useState('1280x720')
  const [job, setJob] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState<any>(null)

  const openPreview = async () => {
    if (prompt.trim().length < 8) return toast.error('Describe the video in at least 8 characters')
    setBusy(true)
    try {
      const r = await api.post('/authoring/video/preview', { model, duration })
      setPreview(r.data)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Preview failed')
    } finally { setBusy(false) }
  }

  const confirm = async () => {
    setPreview(null)
    setBusy(true)
    try {
      const r = await api.post('/authoring/video/generate', {
        prompt: prompt.trim(), slide_id: slide.id, model, size, duration,
      })
      toast.success(`Job started · est. ${Math.round(r.data.estimated_wait_seconds / 60)} min`)
      setJob({ id: r.data.job_id, status: 'PENDING' })
      poll(r.data.job_id)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Video job failed to start')
    } finally { setBusy(false) }
  }

  const poll = async (id: number) => {
    for (let i = 0; i < 200; i++) {
      await new Promise(r => setTimeout(r, 3000))
      try {
        const r = await api.get(`/authoring/video/${id}`)
        setJob(r.data)
        if (r.data.status === 'COMPLETED') { onUpdated(); toast.success('Video ready!'); break }
        if (r.data.status === 'FAILED') { toast.error(r.data.error_log || 'Job failed'); break }
      } catch { /* keep polling */ }
    }
  }

  const isVideo = slide.slide_type === 'VIDEO' && slide.media_url
  return (
    <div className="mt-3 rounded-xl border border-purple-100 bg-purple-50/40 p-3 space-y-2" data-testid="video-editor">
      <div className="flex items-center gap-2 text-xs font-semibold text-purple-800">
        🎬 AI video overview <span className="text-slate-500 font-normal">(Sora 2 · 2-6 min)</span>
      </div>
      {isVideo && (
        <video src={slide.media_url} controls className="rounded-lg max-h-40 w-full bg-black" data-testid="video-preview" />
      )}
      <textarea rows={2} value={prompt} onChange={e => setPrompt(e.target.value)}
        placeholder="Describe the video scene / topic…"
        className="w-full text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-400"
        data-testid="video-prompt-input" />
      <div className="flex flex-wrap items-center gap-2">
        <select value={model} onChange={e => setModel(e.target.value as any)}
          className="text-xs border border-slate-200 bg-white rounded px-2 py-1"
          data-testid="video-model-select">
          <option value="sora-2">sora-2</option>
          <option value="sora-2-pro">sora-2-pro (higher quality)</option>
        </select>
        <select value={duration} onChange={e => setDuration(Number(e.target.value) as any)}
          className="text-xs border border-slate-200 bg-white rounded px-2 py-1"
          data-testid="video-duration-select">
          <option value={4}>4s</option>
          <option value={8}>8s</option>
          <option value={12}>12s</option>
        </select>
        <select value={size} onChange={e => setSize(e.target.value)}
          className="text-xs border border-slate-200 bg-white rounded px-2 py-1"
          data-testid="video-size-select">
          <option value="1280x720">1280×720 (HD)</option>
          <option value="1792x1024">1792×1024 (wide)</option>
          <option value="1024x1792">1024×1792 (portrait)</option>
          <option value="1024x1024">1024×1024 (square)</option>
        </select>
        <button onClick={openPreview} disabled={busy || (job && ['PENDING', 'RUNNING'].includes(job.status))}
          data-testid="video-generate-btn"
          className="text-xs bg-purple-600 hover:bg-purple-700 disabled:bg-slate-300 text-white rounded-lg px-3 py-1.5 font-semibold">
          {busy ? 'Loading…' : (job && ['PENDING', 'RUNNING'].includes(job.status)) ? 'Generating…' : isVideo ? 'Re-generate video' : 'Generate video'}
        </button>
      </div>
      {job && (
        <p className="text-[11px] text-purple-700" data-testid="video-job-status">
          Job #{job.id} · <span className="font-semibold">{job.status}</span>
          {job.status === 'RUNNING' && ' · rendering — safe to leave and come back'}
          {job.error_log && ` · ${job.error_log.slice(0, 100)}`}
        </p>
      )}
      {preview && <SpendPreviewModal preview={preview} onCancel={() => setPreview(null)} onConfirm={confirm} />}
    </div>
  )
}

function SpendPreviewModal({ preview, onCancel, onConfirm }:
  { preview: any; onCancel: () => void; onConfirm: () => void }) {
  const cost = preview.estimated_cost_cents
  const remaining = preview.budget?.remaining_cents ?? null
  const willExceed = preview.will_exceed_budget
  const cents = (c: number) => `${(c / 100).toFixed(2)}`
  return (
    <div className="fixed inset-0 bg-slate-900/50 z-50 flex items-center justify-center p-4" data-testid="video-spend-modal">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4">
        <div className="flex items-center gap-2 text-purple-800">
          <span className="text-2xl">🎬</span>
          <h3 className="text-lg font-bold">Confirm video generation</h3>
        </div>
        <div className="bg-purple-50 border border-purple-100 rounded-xl p-4 space-y-3">
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-slate-500 uppercase tracking-wide">Estimated cost</span>
            <span className="text-2xl font-bold text-purple-700 tabular-nums" data-testid="video-spend-cost">
              ${cents(cost)}
            </span>
          </div>
          {remaining != null && (
            <div className="flex items-baseline justify-between text-sm">
              <span className="text-slate-500">Remaining this month</span>
              <span className={`font-semibold ${willExceed ? 'text-rose-600' : 'text-purple-700'}`} data-testid="video-spend-remaining">
                ${cents(remaining)}
              </span>
            </div>
          )}
          {willExceed && (
            <p className="text-xs text-rose-600 font-medium" data-testid="video-spend-warning">
              ⚠️ This will exceed your monthly budget. The video will still be generated, but future spend may be restricted.
            </p>
          )}
        </div>
        <div className="flex gap-3">
          <button onClick={onCancel} className="flex-1 px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-50">
            Cancel
          </button>
          <button onClick={onConfirm} className="flex-1 px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-sm font-medium">
            Confirm & generate
          </button>
        </div>
      </div>
    </div>
  )
}

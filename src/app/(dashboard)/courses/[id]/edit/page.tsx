"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Save, Plus, Trash2, GripVertical, Eye, FileText, Video, Music, Image, CheckCircle2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

const SLIDE_TYPES = [
  { type: "TEXT",  label: "Text & Media", icon: FileText, color: "bg-blue-100 text-blue-600" },
  { type: "VIDEO", label: "Video",        icon: Video,    color: "bg-purple-100 text-purple-600" },
  { type: "AUDIO", label: "Audio",        icon: Music,    color: "bg-green-100 text-green-600" },
  { type: "IMAGE", label: "Image",        icon: Image,    color: "bg-yellow-100 text-yellow-600" },
  { type: "PDF",   label: "PDF",          icon: FileText, color: "bg-red-100 text-red-600" },
]

interface Slide {
  id: string; title: string; slideType: string; content: string; mediaUrl?: string; order: number
  _local?: boolean // not yet saved
}

interface Course {
  id: string; title: string; description: string | null; category: string | null
  coverColor: string; duration: number | null; isPublished: boolean; passingScore: number
  slides: Slide[]
}

export default function EditCoursePage() {
  const params = useParams()
  const router = useRouter()
  const courseId = params.id as string

  const [course, setCourse] = useState<Course | null>(null)
  const [slides, setSlides] = useState<Slide[]>([])
  const [activeSlide, setActiveSlide] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<Date | null>(null)
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    const res = await fetch(`/api/courses/${courseId}`)
    if (!res.ok) { setLoading(false); return }
    const data: Course = await res.json()
    setCourse(data)
    const sorted = [...data.slides].sort((a, b) => a.order - b.order)
    setSlides(sorted)
    if (sorted.length > 0) setActiveSlide(sorted[0].id)
    setLoading(false)
  }, [courseId])

  useEffect(() => { load() }, [load])

  const saveCourse = async () => {
    if (!course) return
    setSaving(true); setError("")
    try {
      // Save metadata
      const res = await fetch(`/api/courses/${courseId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: course.title,
          description: course.description,
          category: course.category,
          duration: course.duration ? Number(course.duration) : null,
          isPublished: course.isPublished,
          passingScore: Number(course.passingScore),
        }),
      })
      if (!res.ok) { setError("Failed to save course metadata"); return }

      // Save slide content for existing slides
      for (const slide of slides.filter(s => !s._local)) {
        await fetch(`/api/courses/${courseId}/slides`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: slide.id, title: slide.title, content: slide.content, mediaUrl: slide.mediaUrl, slideType: slide.slideType }),
        }).catch(() => {})
      }

      // Create new local slides
      for (const slide of slides.filter(s => s._local)) {
        const r = await fetch(`/api/courses/${courseId}/slides`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: slide.title, content: slide.content, mediaUrl: slide.mediaUrl, slideType: slide.slideType, order: slide.order }),
        })
        if (r.ok) {
          const saved = await r.json()
          setSlides(prev => prev.map(s => s.id === slide.id ? { ...saved } : s))
        }
      }

      setSavedAt(new Date())
    } finally { setSaving(false) }
  }

  const addSlide = (type = "TEXT") => {
    const newSlide: Slide = {
      id: `local-${Date.now()}`,
      title: `Slide ${slides.length + 1}`,
      slideType: type,
      content: "",
      order: slides.length + 1,
      _local: true,
    }
    setSlides(prev => [...prev, newSlide])
    setActiveSlide(newSlide.id)
  }

  const deleteSlide = async (id: string) => {
    const slide = slides.find(s => s.id === id)
    if (!slide) return
    if (!slide._local) {
      await fetch(`/api/courses/${courseId}/slides`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      }).catch(() => {})
    }
    const remaining = slides.filter(s => s.id !== id)
    setSlides(remaining)
    if (activeSlide === id) setActiveSlide(remaining[0]?.id ?? null)
  }

  const updateSlide = (id: string, updates: Partial<Slide>) => {
    setSlides(prev => prev.map(s => s.id === id ? { ...s, ...updates } : s))
  }

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (!course) return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-gray-500">Course not found.</p>
    </div>
  )

  const active = slides.find(s => s.id === activeSlide)

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Left: slide list */}
      <div className="w-64 bg-white border-r flex flex-col flex-shrink-0">
        <div className="p-4 border-b">
          <Link href="/courses" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-3">
            <ArrowLeft className="h-4 w-4" /> All courses
          </Link>
          <input value={course.title} onChange={e => setCourse({ ...course, title: e.target.value })}
            className="w-full font-semibold text-gray-900 text-sm border-b border-transparent focus:border-indigo-300 focus:outline-none pb-0.5 bg-transparent"
            placeholder="Course title" />
          <p className="text-xs text-gray-400 mt-1">{slides.length} slides</p>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {slides.map((s, i) => (
            <div key={s.id}
              onClick={() => setActiveSlide(s.id)}
              className={`flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer mb-0.5 group ${s.id === activeSlide ? "bg-indigo-50 text-indigo-700" : "hover:bg-gray-50 text-gray-600"}`}>
              <GripVertical className="h-3.5 w-3.5 text-gray-300 flex-shrink-0" />
              <span className="text-xs flex-1 truncate">{i + 1}. {s.title || "Untitled"}</span>
              {s._local && <span className="text-[10px] text-amber-500 font-medium">unsaved</span>}
              <button onClick={e => { e.stopPropagation(); deleteSlide(s.id) }}
                className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-opacity flex-shrink-0">
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
        <div className="p-3 border-t">
          <button onClick={() => addSlide("TEXT")}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 border-2 border-dashed border-gray-200 rounded-lg text-xs text-gray-400 hover:border-indigo-300 hover:text-indigo-600 transition-colors">
            <Plus className="h-3.5 w-3.5" /> Add Slide
          </button>
        </div>
      </div>

      {/* Center: slide editor */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="bg-white border-b px-5 py-3 flex items-center gap-3 flex-shrink-0">
          <div className="flex-1">
            {error && (
              <div className="flex items-center gap-2 text-sm text-red-600">
                <AlertCircle className="h-4 w-4" /> {error}
              </div>
            )}
            {savedAt && !error && (
              <div className="flex items-center gap-2 text-sm text-green-600">
                <CheckCircle2 className="h-4 w-4" /> Saved {savedAt.toLocaleTimeString()}
              </div>
            )}
          </div>
          <Link href={`/learn/${courseId}`} target="_blank">
            <Button variant="outline" size="sm" className="gap-1.5 text-xs"><Eye className="h-3.5 w-3.5" /> Preview</Button>
          </Link>
          <Button onClick={saveCourse} disabled={saving} size="sm"
            className="gap-1.5 text-xs bg-indigo-600 hover:bg-indigo-700">
            {saving ? <><div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" /> Saving…</> : <><Save className="h-3.5 w-3.5" /> Save</>}
          </Button>
        </div>

        {active ? (
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-3xl mx-auto space-y-4">
              <input value={active.title} onChange={e => updateSlide(active.id, { title: e.target.value })}
                className="w-full text-xl font-semibold text-gray-900 border-b border-gray-200 focus:border-indigo-400 focus:outline-none pb-1 bg-transparent"
                placeholder="Slide title" />
              <div className="flex gap-2 flex-wrap">
                {SLIDE_TYPES.map(t => (
                  <button key={t.type} onClick={() => updateSlide(active.id, { slideType: t.type })}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${active.slideType === t.type ? t.color + " ring-2 ring-indigo-400" : "bg-gray-100 text-gray-500 hover:bg-gray-200"}`}>
                    {t.label}
                  </button>
                ))}
              </div>
              <textarea value={active.content} onChange={e => updateSlide(active.id, { content: e.target.value })}
                rows={16}
                className="w-full border border-gray-200 rounded-xl p-4 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-indigo-400"
                placeholder={active.slideType === "TEXT" ? "Enter HTML content (e.g. <h2>Title</h2><p>Content…</p>)" : "Enter media URL (video embed, audio URL, image URL, or PDF URL)"} />
              {active.slideType !== "TEXT" && (
                <input value={active.mediaUrl ?? ""} onChange={e => updateSlide(active.id, { mediaUrl: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  placeholder="Media URL (video, audio, image, or PDF)" />
              )}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-400">
              <FileText className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p>Select a slide to edit, or add a new one</p>
            </div>
          </div>
        )}
      </div>

      {/* Right: course settings */}
      <div className="w-72 bg-white border-l flex flex-col flex-shrink-0">
        <div className="p-4 border-b">
          <h3 className="font-semibold text-gray-900 text-sm">Course Settings</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Description</label>
            <textarea value={course.description ?? ""} onChange={e => setCourse({ ...course, description: e.target.value })}
              rows={4} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="Course description" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Category</label>
            <input value={course.category ?? ""} onChange={e => setCourse({ ...course, category: e.target.value })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="e.g. Compliance, Finance" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Duration (minutes)</label>
            <input type="number" min={0} value={course.duration ?? ""} onChange={e => setCourse({ ...course, duration: e.target.value ? Number(e.target.value) : null })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Passing score (%)</label>
            <input type="number" min={0} max={100} value={course.passingScore} onChange={e => setCourse({ ...course, passingScore: Number(e.target.value) })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={course.isPublished} onChange={e => setCourse({ ...course, isPublished: e.target.checked })}
                className="rounded border-gray-300 text-indigo-600" />
              <span className="text-sm text-gray-700">Published</span>
            </label>
          </div>
          <div className="pt-2">
            <Button onClick={saveCourse} disabled={saving} className="w-full gap-2 bg-indigo-600 hover:bg-indigo-700 text-sm">
              {saving ? "Saving…" : "Save Changes"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

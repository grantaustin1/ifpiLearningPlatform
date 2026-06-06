"use client"

import { useState } from "react"
import Link from "next/link"
import { ArrowLeft, Plus, Trash2, GripVertical, Image, Video, FileText, Music, Upload, Save, Eye } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

const slideTypes = [
  { type: "TEXT", label: "Text & Media", icon: FileText, color: "bg-blue-100 text-blue-600" },
  { type: "VIDEO", label: "Video", icon: Video, color: "bg-purple-100 text-purple-600" },
  { type: "AUDIO", label: "Audio", icon: Music, color: "bg-green-100 text-green-600" },
  { type: "IMAGE", label: "Image", icon: Image, color: "bg-yellow-100 text-yellow-600" },
  { type: "PDF", label: "PDF", icon: FileText, color: "bg-red-100 text-red-600" },
]

interface Slide {
  id: string
  title: string
  type: string
  content: string
}

export default function NewCoursePage() {
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [category, setCategory] = useState("")
  const [slides, setSlides] = useState<Slide[]>([
    { id: "1", title: "Introduction", type: "TEXT", content: "" },
  ])
  const [activeSlide, setActiveSlide] = useState("1")
  const [saving, setSaving] = useState(false)

  const addSlide = (type: string) => {
    const newSlide: Slide = {
      id: Date.now().toString(),
      title: `Slide ${slides.length + 1}`,
      type,
      content: "",
    }
    setSlides([...slides, newSlide])
    setActiveSlide(newSlide.id)
  }

  const updateSlide = (id: string, updates: Partial<Slide>) => {
    setSlides(slides.map(s => s.id === id ? { ...s, ...updates } : s))
  }

  const removeSlide = (id: string) => {
    const filtered = slides.filter(s => s.id !== id)
    setSlides(filtered)
    if (activeSlide === id && filtered.length > 0) {
      setActiveSlide(filtered[0].id)
    }
  }

  const active = slides.find(s => s.id === activeSlide)

  return (
    <div className="flex flex-col h-screen">
      {/* Top bar */}
      <div className="border-b bg-white px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/courses">
            <Button variant="ghost" size="sm" className="gap-2">
              <ArrowLeft className="h-4 w-4" /> Back
            </Button>
          </Link>
          <div>
            <input
              className="text-lg font-semibold bg-transparent border-none focus:outline-none focus:ring-0 placeholder-gray-400"
              placeholder="Course title..."
              value={title}
              onChange={e => setTitle(e.target.value)}
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-2">
            <Eye className="h-4 w-4" /> Preview
          </Button>
          <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700 gap-2" disabled={saving}>
            <Save className="h-4 w-4" /> {saving ? "Saving..." : "Save & Publish"}
          </Button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Slide panel */}
        <div className="w-64 border-r bg-white flex flex-col overflow-hidden">
          <div className="p-4 border-b">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Slides ({slides.length})</p>
            <div className="space-y-1">
              {slides.map((slide, idx) => (
                <div
                  key={slide.id}
                  className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer group ${
                    activeSlide === slide.id ? "bg-indigo-50 border border-indigo-200" : "hover:bg-gray-50"
                  }`}
                  onClick={() => setActiveSlide(slide.id)}
                >
                  <GripVertical className="h-3 w-3 text-gray-300" />
                  <span className="text-xs text-gray-400 w-4">{idx + 1}</span>
                  <span className="text-sm font-medium text-gray-700 flex-1 truncate">{slide.title}</span>
                  <button
                    className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500"
                    onClick={e => { e.stopPropagation(); removeSlide(slide.id) }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Add Slide</p>
            <div className="space-y-1">
              {slideTypes.map(st => (
                <button
                  key={st.type}
                  onClick={() => addSlide(st.type)}
                  className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 text-left"
                >
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${st.color}`}>
                    <st.icon className="h-3.5 w-3.5" />
                  </div>
                  <span className="text-sm text-gray-700">{st.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Center: Slide editor */}
        <div className="flex-1 overflow-y-auto bg-gray-50 p-8">
          {active ? (
            <div className="max-w-3xl mx-auto">
              <Card className="border-0 shadow-sm">
                <CardContent className="p-8">
                  <input
                    className="w-full text-xl font-bold text-gray-900 bg-transparent border-none focus:outline-none mb-4 placeholder-gray-300"
                    placeholder="Slide title..."
                    value={active.title}
                    onChange={e => updateSlide(active.id, { title: e.target.value })}
                  />
                  <textarea
                    className="w-full min-h-[300px] text-gray-700 bg-transparent border-none focus:outline-none resize-none text-base leading-relaxed placeholder-gray-300"
                    placeholder="Start writing your slide content... You can add text, format it, and embed media."
                    value={active.content}
                    onChange={e => updateSlide(active.id, { content: e.target.value })}
                  />
                  {active.type !== "TEXT" && (
                    <div className="mt-6 border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-indigo-300 cursor-pointer">
                      <Upload className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                      <p className="text-sm font-medium text-gray-600">Upload {active.type.toLowerCase()}</p>
                      <p className="text-xs text-gray-400 mt-1">Click to browse or drag and drop</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              Select or add a slide to start editing
            </div>
          )}
        </div>

        {/* Right: Properties */}
        <div className="w-72 border-l bg-white overflow-y-auto">
          <div className="p-6">
            <h3 className="font-semibold text-gray-900 mb-4">Course Settings</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  className="w-full border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  rows={3}
                  placeholder="What will learners gain from this course?"
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <select
                  className="w-full border rounded-lg p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                >
                  <option value="">Select category</option>
                  <option>Foundation</option>
                  <option>Legal</option>
                  <option>Compliance</option>
                  <option>Advanced</option>
                  <option>Finance</option>
                  <option>Digital</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Cover Image</label>
                <div className="border-2 border-dashed border-gray-200 rounded-lg p-4 text-center cursor-pointer hover:border-indigo-300">
                  <Upload className="h-5 w-5 text-gray-400 mx-auto mb-1" />
                  <p className="text-xs text-gray-500">Upload cover image</p>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Certificate on completion</label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" className="rounded" defaultChecked />
                  <span className="text-sm text-gray-600">Issue certificate automatically</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

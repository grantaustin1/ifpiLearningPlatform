"use client"

import { useState } from "react"
import { Sparkles, X, Loader2, CheckCircle, ChevronDown, ChevronUp, AlertCircle } from "lucide-react"

interface GeneratedSlide { title: string; content: string; slideType: string; order: number }
interface GeneratedQuestion { question: string; questionType: string; options: string[]; correctAnswer: string; explanation: string; points: number; order: number }

interface AIResult { slides: GeneratedSlide[]; questions: GeneratedQuestion[] }

export function AIBuilderModal({ onClose, onApply }: {
  onClose: () => void
  onApply: (result: AIResult) => void
}) {
  const [topic, setTopic] = useState("")
  const [description, setDescription] = useState("")
  const [numSlides, setNumSlides] = useState(5)
  const [includeQuiz, setIncludeQuiz] = useState(true)
  const [numQuestions, setNumQuestions] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [result, setResult] = useState<AIResult | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)

  const handleGenerate = async () => {
    if (!topic.trim()) { setError("Topic is required"); return }
    setLoading(true); setError(""); setResult(null)
    try {
      const res = await fetch("/api/ai/course-builder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, description, numSlides, includeQuiz, numQuestions }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.error ?? "Generation failed"); return }
      setResult(data)
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden max-h-[90vh] flex flex-col">
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
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700"><X className="h-5 w-5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {!result ? (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Topic *</label>
                <input value={topic} onChange={e => setTopic(e.target.value)}
                  placeholder="e.g. Introduction to Music Copyright Law"
                  className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Additional context (optional)</label>
                <textarea value={description} onChange={e => setDescription(e.target.value)}
                  rows={3} placeholder="Audience level, specific focus areas, key concepts to cover..."
                  className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Number of slides</label>
                  <input type="number" min={1} max={20} value={numSlides} onChange={e => setNumSlides(parseInt(e.target.value) || 5)}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Quiz questions</label>
                  <div className="flex items-center gap-2">
                    <input type="checkbox" id="incQuiz" checked={includeQuiz} onChange={e => setIncludeQuiz(e.target.checked)}
                      className="rounded border-slate-300 text-indigo-600" />
                    <label htmlFor="incQuiz" className="text-sm text-slate-600">Include quiz</label>
                  </div>
                  {includeQuiz && (
                    <input type="number" min={1} max={20} value={numQuestions} onChange={e => setNumQuestions(parseInt(e.target.value) || 5)}
                      className="w-full mt-2 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
                  )}
                </div>
              </div>
              {error && (
                <div className="flex items-start gap-2 bg-red-50 border border-red-100 rounded-xl p-3">
                  <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-600">{error}</p>
                </div>
              )}
            </>
          ) : (
            <div className="space-y-4">
              <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4 flex items-start gap-3">
                <CheckCircle className="h-5 w-5 text-emerald-500 flex-shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-emerald-800">Generated successfully!</p>
                  <p className="text-xs text-emerald-600 mt-0.5">
                    {result.slides.length} slides{result.questions.length > 0 ? ` + ${result.questions.length} quiz questions` : ""}
                  </p>
                </div>
              </div>

              <button onClick={() => setPreviewOpen(!previewOpen)}
                className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-100 transition-colors">
                <span>Preview slides</span>
                {previewOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </button>

              {previewOpen && (
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {result.slides.map((s, i) => (
                    <div key={i} className="bg-white border border-slate-100 rounded-xl p-3">
                      <p className="text-sm font-medium text-slate-800">{s.order}. {s.title}</p>
                      <div className="text-xs text-slate-400 mt-1 line-clamp-2"
                        dangerouslySetInnerHTML={{ __html: s.content.replace(/<[^>]+>/g, ' ').substring(0, 120) + '…' }} />
                    </div>
                  ))}
                </div>
              )}

              <p className="text-xs text-slate-500 bg-amber-50 border border-amber-100 rounded-xl p-3">
                <strong>Note:</strong> Applying will create a new course draft. You can edit any slide before publishing.
                {result.questions.length > 0 && " Quiz questions can be reviewed in the Exams section after the course is created."}
              </p>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t flex items-center justify-end gap-3 bg-slate-50">
          {result ? (
            <>
              <button onClick={() => setResult(null)}
                className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition-colors">
                Regenerate
              </button>
              <button onClick={() => onApply(result)}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors">
                <CheckCircle className="h-4 w-4" /> Apply to Course
              </button>
            </>
          ) : (
            <>
              <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition-colors">Cancel</button>
              <button onClick={handleGenerate} disabled={loading || !topic.trim()}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition-colors">
                {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</> : <><Sparkles className="h-4 w-4" /> Generate Course</>}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

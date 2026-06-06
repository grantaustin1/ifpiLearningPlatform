"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { ChevronLeft, ChevronRight, CheckCircle, BookOpen, Menu, X, Star } from "lucide-react"
import { Button } from "@/components/ui/button"

interface Slide {
  id: string; title: string; content: string
  slideType: string; mediaUrl?: string; order: number
}
interface Course {
  id: string; title: string; description?: string; slides: Slide[]
}
interface CompletionResult {
  xpEarned: number; badgesEarned: string[]; alreadyCompleted?: boolean
}

export default function LearnPage() {
  const params = useParams()
  const router = useRouter()
  const [course, setCourse] = useState<Course | null>(null)
  const [current, setCurrent] = useState(0)
  const [completed, setCompleted] = useState<Set<number>>(new Set())
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [loading, setLoading] = useState(true)
  const [finishing, setFinishing] = useState(false)
  const [completionResult, setCompletionResult] = useState<CompletionResult | null>(null)

  useEffect(() => {
    fetch(`/api/courses/${params.courseId}`)
      .then(r => r.json())
      .then(data => { setCourse(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [params.courseId])

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-gray-500">Loading course...</p>
      </div>
    </div>
  )
  if (!course) return <div className="min-h-screen flex items-center justify-center"><p className="text-gray-500">Course not found.</p></div>

  const slide = course.slides[current]
  const progress = course.slides.length > 0 ? (completed.size / course.slides.length) * 100 : 0

  const markCompleteAndNext = async () => {
    const next = new Set(completed).add(current)
    setCompleted(next)
    const isLastSlide = current === course.slides.length - 1
    if (isLastSlide || next.size === course.slides.length) {
      setFinishing(true)
      try {
        const res = await fetch(`/api/courses/${course.id}/complete`, { method: "POST" })
        if (res.ok) setCompletionResult(await res.json())
      } catch {}
      setFinishing(false)
      setCurrent(course.slides.length)
    } else {
      setCurrent(current + 1)
    }
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <div className={`${sidebarOpen ? "w-72" : "w-0"} border-r bg-white flex-shrink-0 overflow-hidden transition-all duration-200`}>
        <div className="p-4 border-b">
          <h2 className="font-semibold text-gray-900 text-sm truncate">{course.title}</h2>
          <div className="mt-2 h-1.5 bg-gray-100 rounded-full">
            <div className="h-1.5 bg-indigo-600 rounded-full transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="text-xs text-gray-500 mt-1">{Math.round(progress)}% complete</p>
        </div>
        <nav className="p-2 overflow-y-auto max-h-[calc(100vh-120px)]">
          {course.slides.map((s, i) => (
            <button key={s.id} onClick={() => setCurrent(i)}
              className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-left text-sm transition-colors mb-0.5 ${
                i === current ? "bg-indigo-50 text-indigo-700 font-medium" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              <span className="w-5 h-5 rounded-full border-2 flex-shrink-0 flex items-center justify-center text-xs">
                {completed.has(i) ? <CheckCircle className="h-4 w-4 text-green-500" /> : i + 1}
              </span>
              <span className="truncate">{s.title}</span>
            </button>
          ))}
        </nav>
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <div className="bg-white border-b px-6 py-3 flex items-center gap-4">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-gray-500 hover:text-gray-900">
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <BookOpen className="h-5 w-5 text-indigo-600" />
          <span className="text-sm font-medium text-gray-700 truncate">{course.title}</span>
          <div className="ml-auto flex items-center gap-2 text-sm text-gray-500">
            <span>{Math.min(current + 1, course.slides.length)} / {course.slides.length}</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {slide ? (
            <div className="max-w-3xl mx-auto px-6 py-10">
              <h1 className="text-2xl font-bold text-gray-900 mb-6">{slide.title}</h1>
              {slide.slideType === "VIDEO" && slide.mediaUrl && (
                <div className="mb-6 rounded-xl overflow-hidden bg-black aspect-video">
                  <iframe src={slide.mediaUrl} className="w-full h-full" allowFullScreen />
                </div>
              )}
              {slide.slideType === "IMAGE" && slide.mediaUrl && (
                <img src={slide.mediaUrl} alt={slide.title} className="mb-6 rounded-xl w-full" />
              )}
              {slide.content && (
                <div className="prose prose-indigo max-w-none text-gray-700 leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: slide.content }} />
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-sm">
                <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
                <h2 className="text-xl font-semibold text-gray-900">Course Complete!</h2>
                <p className="text-gray-500 mt-2">You have finished all slides.</p>
                {completionResult && completionResult.xpEarned > 0 && (
                  <div className="mt-4 inline-flex items-center gap-1.5 bg-amber-50 border border-amber-200 text-amber-700 text-sm font-semibold px-3 py-1.5 rounded-full">
                    <Star className="h-4 w-4" /> +{completionResult.xpEarned} XP earned
                  </div>
                )}
                {completionResult && completionResult.badgesEarned.length > 0 && (
                  <div className="mt-3 bg-indigo-50 border border-indigo-100 rounded-xl p-3">
                    <p className="text-xs font-semibold text-indigo-700 mb-2">
                      Badge{completionResult.badgesEarned.length > 1 ? "s" : ""} unlocked!
                    </p>
                    <div className="flex gap-2 justify-center text-2xl">
                      {completionResult.badgesEarned.map(b => (
                        <span key={b}>{b === "FIRST_COURSE" ? "🎓" : b === "COURSE_MASTER" ? "🏆" : "🏅"}</span>
                      ))}
                    </div>
                  </div>
                )}
                <Button className="mt-6 bg-indigo-600 hover:bg-indigo-700" onClick={() => router.push("/courses")}>
                  Back to Courses
                </Button>
              </div>
            </div>
          )}
        </div>

        {slide && (
          <div className="bg-white border-t px-6 py-4 flex items-center justify-between">
            <Button
              variant="outline"
              onClick={() => setCurrent(Math.max(0, current - 1))}
              disabled={current === 0}
              className="gap-2"
            >
              <ChevronLeft className="h-4 w-4" /> Previous
            </Button>
            <Button
              className="bg-indigo-600 hover:bg-indigo-700 gap-2"
              onClick={markCompleteAndNext}
              disabled={finishing}
            >
              {finishing ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : current < course.slides.length - 1 ? (
                <>Next <ChevronRight className="h-4 w-4" /></>
              ) : (
                <><CheckCircle className="h-4 w-4" /> Complete</>
              )}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

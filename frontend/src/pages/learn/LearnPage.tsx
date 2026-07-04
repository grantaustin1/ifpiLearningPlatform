import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from 'lib/api'
import { ChevronLeft, ChevronRight, CheckCircle, Star } from 'lucide-react'
import { toast } from 'sonner'
import CommentsPanel from 'components/CommentsPanel'
import { AITutorPanel } from 'components/AITutorPanel'

export default function LearnPage() {
  const { courseId } = useParams()
  const nav = useNavigate()
  const [course, setCourse] = useState<any>(null)
  const [current, setCurrent] = useState(0)
  const [completed, setCompleted] = useState<Set<number>>(new Set())
  const [result, setResult] = useState<any>(null)
  const [finishing, setFinishing] = useState(false)

  useEffect(() => {
    (async () => {
      // Make sure the user is enrolled (idempotent)
      try { await api.post(`/courses/${courseId}/enroll`) } catch { /* may already be enrolled */ }
      const r = await api.get(`/courses/${courseId}`)
      setCourse(r.data)
    })()
  }, [courseId])

  const slide = course?.slides?.[current]

  // Iter 26 — Slide-view drop-off tracking. Fire once per (slide,
  // user, day) via the public track-view endpoint. Silent — an error
  // must never derail the player.
  useEffect(() => {
    if (!slide?.id || !courseId) return
    api.post(`/catalog/${courseId}/slides/${slide.id}/track-view`).catch(() => { /* silent */ })
  }, [slide?.id, courseId])

  if (!course) return <div className="flex items-center justify-center h-screen"><div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>

  const progress = course.slides.length ? (completed.size / course.slides.length) * 100 : 0
  const isLast = current === course.slides.length - 1

  const next = async () => {
    const newSet = new Set(completed); newSet.add(current); setCompleted(newSet)
    if (isLast) {
      setFinishing(true)
      try {
        const r = await api.post(`/courses/${courseId}/complete`)
        setResult(r.data)
        toast.success('Course complete! Certificate issued.')
      } catch (e) {
        toast.error('Could not record completion')
      } finally { setFinishing(false); setCurrent(course.slides.length) }
    } else { setCurrent(current + 1) }
  }

  return (
    <div className="flex h-screen bg-slate-50" data-testid="learn-page">
      <aside className="w-72 border-r bg-white overflow-y-auto">
        <div className="p-4 border-b">
          <h2 className="font-semibold text-slate-900 text-sm">{course.title}</h2>
          <div className="mt-2 h-1.5 bg-slate-100 rounded-full"><div className="h-1.5 bg-indigo-600 rounded-full" style={{ width: `${progress}%` }} /></div>
          <p className="text-xs text-slate-500 mt-1">{Math.round(progress)}% complete</p>
          <button onClick={() => nav(`/learn/${courseId}/flashcards`)}
            data-testid="learn-flashcards-link"
            className="mt-3 w-full inline-flex items-center justify-center gap-1.5 text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg py-2">
            ✨ Practice flashcards
          </button>
        </div>
        <nav className="p-2">
          {course.slides.map((s: any, i: number) => (
            <button key={s.id} onClick={() => setCurrent(i)} data-testid={`slide-nav-${i}`}
              className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-left text-sm mb-0.5 ${i === current ? 'bg-indigo-50 text-indigo-700 font-medium' : 'text-slate-600 hover:bg-slate-50'}`}>
              <span className="w-5 h-5 rounded-full border-2 flex-shrink-0 flex items-center justify-center text-xs">
                {completed.has(i) ? <CheckCircle className="h-4 w-4 text-emerald-500" /> : i + 1}
              </span>
              <span className="truncate">{s.title}</span>
            </button>
          ))}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col">
        <div className="bg-white border-b px-5 py-3 text-sm font-medium text-slate-700">{course.title} <span className="text-slate-400 ml-2">{Math.min(current + 1, course.slides.length)} / {course.slides.length}</span></div>
        <div className="flex-1 overflow-y-auto">
          {slide ? (
            <div className="max-w-3xl mx-auto px-6 py-10" data-testid="learn-slide-content">
              <h1 className="text-2xl font-bold text-slate-900 mb-6 font-display">{slide.title}</h1>
              {slide.slide_type === 'VIDEO' && slide.media_url && <div className="mb-6 rounded-xl overflow-hidden bg-black aspect-video"><iframe src={slide.media_url} className="w-full h-full" allowFullScreen title="video" /></div>}
              {slide.slide_type === 'IMAGE' && slide.media_url && <img src={slide.media_url} alt="" className="mb-6 rounded-xl w-full" />}
              {slide.slide_type === 'AUDIO' && slide.media_url && <audio src={slide.media_url} controls className="w-full mb-6" />}
              {slide.slide_type === 'PDF' && slide.media_url && <iframe src={slide.media_url} className="w-full h-[80vh] mb-6 rounded-xl border border-slate-200" title="pdf" />}
              {slide.slide_type === 'SCORM' && slide.media_url && <iframe src={slide.media_url} className="w-full h-[80vh] mb-6 rounded-xl border border-slate-200 bg-white" title="scorm" allow="autoplay; fullscreen" data-testid="scorm-iframe" />}
              {slide.content && <div className="prose prose-indigo max-w-none text-slate-700 leading-relaxed" dangerouslySetInnerHTML={{ __html: slide.content }} />}
              {slide.narration_url && (
                <div className="mt-6 bg-indigo-50 border border-indigo-100 rounded-xl p-3 flex items-center gap-3" data-testid="learn-slide-narration">
                  <span className="text-xs font-semibold text-indigo-700 uppercase tracking-wide">
                    🔊 Narration {slide.narration_voice ? `· ${slide.narration_voice}` : ''}
                  </span>
                  <audio src={slide.narration_url} controls className="flex-1 h-9" />
                </div>
              )}
              <CommentsPanel slideId={slide.id} />
            </div>
          ) : (
            <div className="flex items-center justify-center h-full" data-testid="learn-complete-card">
              <div className="text-center max-w-sm">
                <CheckCircle className="h-16 w-16 text-emerald-500 mx-auto mb-4" />
                <h2 className="text-xl font-semibold">Course Complete!</h2>
                {result?.xp_earned > 0 && (
                  <div className="mt-4 inline-flex items-center gap-1.5 bg-amber-50 border border-amber-200 text-amber-700 text-sm font-semibold px-3 py-1.5 rounded-full">
                    <Star className="h-4 w-4" /> +{result.xp_earned} XP
                  </div>
                )}
                <button onClick={() => nav('/certificates')} className="mt-6 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium">View Certificate</button>
              </div>
            </div>
          )}
        </div>
        {slide && (
          <div className="bg-white border-t px-6 py-4 flex items-center justify-between">
            <button onClick={() => setCurrent(Math.max(0, current - 1))} disabled={current === 0} data-testid="prev-slide-btn"
              className="inline-flex items-center gap-2 border border-slate-200 rounded-lg px-4 py-2 text-sm disabled:opacity-50"><ChevronLeft className="h-4 w-4" /> Previous</button>
            <button onClick={next} disabled={finishing} data-testid="next-slide-btn"
              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-50">
              {finishing ? 'Finishing…' : (isLast ? <><CheckCircle className="h-4 w-4" /> Complete</> : <>Next <ChevronRight className="h-4 w-4" /></>)}
            </button>
          </div>
        )}
      </div>
      <AITutorPanel courseId={course.id} />
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from 'lib/api'
import { safeHtml } from 'lib/sanitize'
import { ChevronLeft, ChevronRight, CheckCircle, ClipboardList, Star, Pencil } from 'lucide-react'
import { toast } from 'sonner'
import CommentsPanel from 'components/CommentsPanel'
import { AITutorPanel } from 'components/AITutorPanel'
import { useAuth } from 'contexts/AuthContext'

export default function LearnPage() {
  const { courseId } = useParams()
  const nav = useNavigate()
  const { hasRole } = useAuth()
  const isStaff = hasRole('ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR')
  const [course, setCourse] = useState<any>(null)
  const [current, setCurrent] = useState(0)
  const [completed, setCompleted] = useState<Set<number>>(new Set())
  const [result, setResult] = useState<any>(null)
  const [myRating, setMyRating] = useState(0)
  const [hoverRating, setHoverRating] = useState(0)
  const [ratingBusy, setRatingBusy] = useState(false)
  const [reviewText, setReviewText] = useState('')
  const [reviewSaved, setReviewSaved] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    (async () => {
      // Make sure the user is enrolled (idempotent)
      try { await api.post(`/courses/${courseId}/enroll`) } catch { /* may already be enrolled */ }
      try {
        const r = await api.get(`/courses/${courseId}`)
        setCourse(r.data)
      } catch {
        setLoadError(true)
      }
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

  if (loadError) return (
    <div className="flex items-center justify-center h-screen bg-slate-50" data-testid="course-unavailable">
      <div className="text-center max-w-md px-6">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
          <ClipboardList className="h-7 w-7 text-slate-400" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">This course isn't available</h2>
        <p className="text-sm text-slate-500 mt-2">
          It may have been unpublished, archived or removed. If you think this is a
          mistake, ask your academy administrator.
        </p>
        <button onClick={() => nav('/courses')} data-testid="back-to-courses-btn"
          className="mt-6 inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg px-5 py-2.5">
          <ChevronLeft className="h-4 w-4" /> Back to My Courses
        </button>
      </div>
    </div>
  )

  if (!course) return <div className="flex items-center justify-center h-screen"><div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>

  const progress = course.slides.length ? (completed.size / course.slides.length) * 100 : 0
  const isLast = current === course.slides.length - 1
  // Iter 49 — Exam gate: courses with a published exam route the learner
  // to the exam; the certificate is issued after they pass it.
  const examGate = Boolean(course.exam_id) && !course.exam_passed

  const next = async () => {
    const newSet = new Set(completed); newSet.add(current); setCompleted(newSet)
    if (isLast) {
      setCompleted(new Set(course.slides.map((_: unknown, i: number) => i)))
      if (examGate) {
        toast.info(`Pass "${course.exam_title || 'the course exam'}" to earn your certificate.`)
        nav(`/take/${course.exam_id}`)
        return
      }
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
        <div className="bg-white border-b px-5 py-3 text-sm font-medium text-slate-700 flex items-center">
          <span>{course.title} <span className="text-slate-400 ml-2">{Math.min(current + 1, course.slides.length)} / {course.slides.length}</span></span>
          {isStaff && (
            <button onClick={() => nav(`/courses/${courseId}/edit`)} data-testid="learn-edit-course-btn"
              title="Open this course in the editor to change slides, pictures and layout"
              className="ml-auto inline-flex items-center gap-1.5 text-sm font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-4 py-2 shadow-sm shadow-indigo-200 transition-colors">
              <Pencil className="h-4 w-4" /> Edit course
            </button>
          )}
        </div>
        {examGate && slide && (
          <div data-testid="exam-gate-banner"
            className="bg-amber-50 border-b border-amber-200 px-5 py-2.5 text-sm text-amber-800 flex items-center gap-2">
            <ClipboardList className="h-4 w-4 flex-shrink-0" />
            <span>This course ends with an exam — pass <strong>{course.exam_title || 'the course exam'}</strong> to earn your certificate.</span>
          </div>
        )}
        <div className="flex-1 overflow-y-auto">
          {slide ? (
            <div className="max-w-3xl mx-auto px-6 py-10" data-testid="learn-slide-content">
              <h1 className="text-2xl font-bold text-slate-900 mb-6 font-display">{slide.title}</h1>
              {slide.slide_type === 'VIDEO' && slide.media_url && <div className="mb-6 rounded-xl overflow-hidden bg-black aspect-video"><iframe src={slide.media_url} className="w-full h-full" allowFullScreen title="video" /></div>}
              {slide.slide_type === 'IMAGE' && slide.media_url ? (
                <ImageSlideLayout slide={slide} html={slide.content ? safeHtml(slide.content) : ''} />
              ) : (
                <>
                  {slide.slide_type === 'AUDIO' && slide.media_url && <audio src={slide.media_url} controls className="w-full mb-6" />}
                  {slide.slide_type === 'PDF' && slide.media_url && <iframe src={slide.media_url} className="w-full h-[80vh] mb-6 rounded-xl border border-slate-200" title="pdf" />}
                  {slide.slide_type === 'SCORM' && slide.media_url && <iframe src={slide.media_url} className="w-full h-[80vh] mb-6 rounded-xl border border-slate-200 bg-white" title="scorm" allow="autoplay; fullscreen" data-testid="scorm-iframe" />}
                  {slide.content && <div className="prose prose-indigo max-w-none text-slate-700 leading-relaxed" dangerouslySetInnerHTML={{ __html: safeHtml(slide.content) }} />}
                </>
              )}
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
                <div className="mt-6 bg-slate-50 border border-slate-200 rounded-xl p-4" data-testid="course-rating-block">
                  <p className="text-sm font-medium text-slate-700 mb-2">{myRating ? 'Thanks for rating this course!' : 'How was this course?'}</p>
                  <div className="flex items-center justify-center gap-1">
                    {[1, 2, 3, 4, 5].map(n => (
                      <button key={n} disabled={ratingBusy}
                        onClick={async () => {
                          setRatingBusy(true)
                          try {
                            await api.post(`/courses/${courseId}/rating`, { rating: n })
                            setMyRating(n)
                            toast.success('Rating saved — thank you!')
                          } catch (e: any) { toast.error(e?.response?.data?.detail || 'Could not save rating') }
                          finally { setRatingBusy(false) }
                        }}
                        onMouseEnter={() => setHoverRating(n)} onMouseLeave={() => setHoverRating(0)}
                        data-testid={`rate-star-${n}`}
                        className="p-0.5 transition-transform hover:scale-110">
                        <Star className={`h-7 w-7 ${(hoverRating || myRating) >= n ? 'text-amber-400 fill-amber-400' : 'text-slate-300'}`} />
                      </button>
                    ))}
                  </div>
                  {myRating > 0 && !reviewSaved && (
                    <div className="mt-3 text-left" data-testid="review-comment-block">
                      <textarea value={reviewText} onChange={e => setReviewText(e.target.value)}
                        rows={3} maxLength={500} data-testid="review-comment-input"
                        placeholder="Add a short review (optional) — what did you like?"
                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400" />
                      <button disabled={ratingBusy || !reviewText.trim()} data-testid="submit-review-btn"
                        onClick={async () => {
                          setRatingBusy(true)
                          try {
                            await api.post(`/courses/${courseId}/rating`, { rating: myRating, comment: reviewText.trim() })
                            setReviewSaved(true)
                            toast.success('Review saved — thank you!')
                          } catch (e: any) { toast.error(e?.response?.data?.detail || 'Could not save review') }
                          finally { setRatingBusy(false) }
                        }}
                        className="mt-2 w-full bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg py-2 disabled:opacity-50">
                        Submit review
                      </button>
                    </div>
                  )}
                  {reviewSaved && (
                    <p className="mt-2 text-xs text-emerald-600 font-medium" data-testid="review-saved-note">Your review may appear on the course page.</p>
                  )}
                </div>
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
              {finishing ? 'Finishing…' : (isLast
                ? (examGate
                  ? <><CheckCircle className="h-4 w-4" /> Take exam</>
                  : <><CheckCircle className="h-4 w-4" /> Complete</>)
                : <>Next <ChevronRight className="h-4 w-4" /></>)}
            </button>
          </div>
        )}
      </div>
      <AITutorPanel courseId={course.id} />
    </div>
  )
}

function ImageSlideLayout({ slide, html }: { slide: any; html: string }) {
  const pos = slide.image_position || 'above'
  const body = html
    ? <div className="prose prose-indigo max-w-none text-slate-700 leading-relaxed" dangerouslySetInnerHTML={{ __html: html }} />
    : null
  if (pos === 'beside') return (
    <div className="grid md:grid-cols-2 gap-6 items-start mb-6" data-testid="image-layout-beside">
      <img src={slide.media_url} alt="" className="rounded-xl w-full" data-testid="learn-slide-image" />
      {body}
    </div>
  )
  if (pos === 'behind') return (
    <div className="relative rounded-xl overflow-hidden mb-6" data-testid="image-layout-behind">
      <img src={slide.media_url} alt="" className="absolute inset-0 w-full h-full object-cover" data-testid="learn-slide-image" />
      <div className="absolute inset-0 bg-slate-900/60" />
      <div className="relative p-8 min-h-[320px] flex items-center">
        {html
          ? <div className="prose prose-invert max-w-none leading-relaxed" dangerouslySetInnerHTML={{ __html: html }} />
          : <span />}
      </div>
    </div>
  )
  return (
    <div className="mb-6" data-testid="image-layout-above">
      <img src={slide.media_url} alt="" className="rounded-xl w-full" data-testid="learn-slide-image" />
      {body && <div className="mt-6">{body}</div>}
    </div>
  )
}

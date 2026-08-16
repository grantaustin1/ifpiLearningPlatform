import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
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
  const [searchParams] = useSearchParams()
  const searchSlide = searchParams.get('slide')
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
      let resumeAt = 0
      // Make sure the user is enrolled (idempotent)
      try {
        const er = await api.post(`/courses/${courseId}/enroll`)
        resumeAt = er.data?.last_slide_index || 0
      } catch { /* may already be enrolled */ }
      try {
        const r = await api.get(`/courses/${courseId}`)
        setCourse(r.data)
        const wanted = Number(searchSlide)
        if (wanted) {
          const idx = (r.data.slides || []).findIndex((s: any) => s.id === wanted)
          if (idx >= 0) setCurrent(idx)
        } else if (resumeAt > 0 && resumeAt < (r.data.slides || []).length) {
          setCurrent(resumeAt)
          toast.info('Resumed where you left off', { duration: 2500 })
        }
      } catch {
        setLoadError(true)
      }
    })()
  }, [courseId, searchSlide])

  const progressTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (!course) return
    if (progressTimer.current) clearTimeout(progressTimer.current)
    progressTimer.current = setTimeout(() => {
      api.post(`/courses/${courseId}/progress`, { slide_index: current }).catch(() => {})
    }, 600)
    return () => { if (progressTimer.current) clearTimeout(progressTimer.current) }
  }, [current, course, courseId])

  const slide = course?.slides?.[current]
  if (loadError) return null
  if (!course) return null
  return null
}

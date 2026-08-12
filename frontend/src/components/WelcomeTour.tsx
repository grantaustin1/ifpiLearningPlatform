import { useEffect, useLayoutEffect, useState } from 'react'
import { useAuth } from 'contexts/AuthContext'
import { Sparkles } from 'lucide-react'

type Step = {
  selector: string | null
  title: string
  body: string
}

const LEARNER_STEPS: Step[] = [
  { selector: null, title: 'Welcome to IFPI Learning!', body: 'Here\'s a quick 30-second tour so you know exactly where to start. You can skip anytime.' },
  { selector: '[data-testid="nav-courses"]', title: 'Start here: My Courses', body: 'All your courses live here. Open one and press "Start Course" to begin learning slide by slide.' },
  { selector: '[data-testid="nav-certificates"]', title: 'Your certificates', body: 'Pass a course exam and your certificate appears here — download it as a PDF or share a verification link.' },
  { selector: '[data-testid="sidebar-help-link"]', title: 'Help & guides', body: 'Stuck? The Student User Guide (PDF) walks through every feature.' },
  { selector: '[data-testid="feedback-widget-btn"]', title: 'Spot a problem?', body: 'Click this button anytime to report an issue or share an idea — you can even attach a screenshot. Your feedback goes straight to the team.' },
]

const ADMIN_STEPS: Step[] = [
  { selector: null, title: 'Welcome to IFPI Learning!', body: 'Here\'s a quick 30-second tour of the admin portal. You can skip anytime.' },
  { selector: '[data-testid="nav-dashboard"]', title: 'Your dashboard', body: 'Enrolments, completions and activity at a glance — check in here daily.' },
  { selector: '[data-testid="nav-courses"]', title: 'Courses', body: 'Create and edit courses, upload slides and covers, and publish when ready.' },
  { selector: '[data-testid="nav-exams"]', title: 'Exams & insights', body: 'Build exams, review attempts and see which questions learners miss most.' },
  { selector: '[data-testid="nav-feedback-admin"]', title: 'Tester feedback', body: 'Everything reported via the in-app "Report an issue" button lands here, screenshots included.' },
  { selector: '[data-testid="feedback-widget-btn"]', title: 'Report an issue', body: 'You can use the feedback button too — notes and screenshots all collect in one place.' },
]

const doneKey = (userId: number | string) => `ifpi_tour_done_v1_${userId}`

export function WelcomeTour() {
  const { user, hasRole } = useAuth()
  const isAdmin = hasRole('ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR')
  const [active, setActive] = useState(false)
  const [idx, setIdx] = useState(0)
  const [rect, setRect] = useState<DOMRect | null>(null)
  const [steps, setSteps] = useState<Step[]>([])

  const step = steps[idx]

  useEffect(() => {
    if (!user?.id) return
    if (localStorage.getItem(doneKey(user.id))) return
    const t = window.setTimeout(() => {
      setSteps((isAdmin ? ADMIN_STEPS : LEARNER_STEPS)
        .filter(s => !s.selector || !!document.querySelector(s.selector)))
      setActive(true)
    }, 900)
    return () => window.clearTimeout(t)
  }, [user?.id, isAdmin])

  useLayoutEffect(() => {
    if (!active || !step) return
    const measure = () => {
      if (!step.selector) { setRect(null); return }
      const el = document.querySelector(step.selector)
      if (!el) { setRect(null); return }
      el.scrollIntoView({ block: 'center', behavior: 'instant' as ScrollBehavior })
      setRect(el.getBoundingClientRect())
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [active, idx, step?.selector])

  if (!active || !step) return null

  const finish = () => {
    if (user?.id) localStorage.setItem(doneKey(user.id), new Date().toISOString())
    setActive(false)
  }
  const next = () => { if (idx + 1 >= steps.length) finish(); else setIdx(idx + 1) }
  const last = idx === steps.length - 1

  const spotlight = step.selector && rect
  const pad = 6
  const tooltipStyle: React.CSSProperties = spotlight
    ? (rect!.left < window.innerWidth / 2
        ? { top: Math.min(Math.max(rect!.top - 20, 16), window.innerHeight - 240), left: rect!.right + 18 }
        : { top: Math.max(rect!.top - 190, 16), left: Math.max(rect!.left - 340, 16) })
    : { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }

  return (
    <div className="fixed inset-0 z-[70]" data-testid="welcome-tour">
      {spotlight ? (
        <div
          className="absolute rounded-xl transition-all duration-300 pointer-events-none"
          style={{
            top: rect!.top - pad, left: rect!.left - pad,
            width: rect!.width + pad * 2, height: rect!.height + pad * 2,
            boxShadow: '0 0 0 9999px rgba(2, 6, 23, 0.72)',
            border: '2px solid rgba(129, 140, 248, 0.9)',
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-slate-950/72" style={{ backgroundColor: 'rgba(2,6,23,0.72)' }} />
      )}
      <div className="absolute w-80 bg-white rounded-2xl shadow-2xl border border-slate-200 p-5" style={tooltipStyle} data-testid="welcome-tour-card">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center flex-shrink-0">
            <Sparkles className="h-3.5 w-3.5 text-white" />
          </div>
          <p className="text-sm font-bold text-slate-900" data-testid="welcome-tour-title">{step.title}</p>
        </div>
        <p className="text-[13px] text-slate-600 leading-relaxed" data-testid="welcome-tour-body">{step.body}</p>
        <div className="flex items-center justify-between mt-4">
          <div className="flex gap-1">
            {steps.map((_, i) => (
              <span key={i} className={`w-1.5 h-1.5 rounded-full ${i === idx ? 'bg-indigo-500' : 'bg-slate-200'}`} />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {!last && (
              <button onClick={finish} data-testid="welcome-tour-skip"
                className="text-xs font-medium text-slate-400 hover:text-slate-600 px-2 py-1.5">
                Skip tour
              </button>
            )}
            <button onClick={next} data-testid="welcome-tour-next"
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg px-4 py-1.5 transition-colors">
              {last ? 'Got it, let\'s go!' : idx === 0 ? 'Show me around' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

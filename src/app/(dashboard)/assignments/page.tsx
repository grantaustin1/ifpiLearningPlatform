"use client"

import { useState, useEffect } from "react"
import { ClipboardList, Star, Check, ChevronDown, ChevronUp, ExternalLink, Loader2 } from "lucide-react"

interface Submission {
  id: string; userId: string; status: string; score: number | null; feedback: string | null
  content: string | null; fileUrl: string | null; fileName: string | null
  submittedAt: string; gradedAt: string | null
  user: { id: string; name: string | null; email: string }
}

interface AssignmentWithSubs {
  assignment: { id: string; title: string; maxScore: number; courseId: string }
  submissions: Submission[]
}

interface CourseRow {
  id: string; title: string
  assignments: { id: string; title: string; _count: { submissions: number } }[]
}

function timeAgo(iso: string) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return "just now"
  const m = Math.floor(s / 60); if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

const STATUS_BADGE: Record<string, string> = {
  SUBMITTED: "bg-indigo-100 text-indigo-700",
  GRADED:    "bg-emerald-100 text-emerald-700",
  RETURNED:  "bg-amber-100 text-amber-700",
}

export default function AssignmentsPage() {
  const [courses, setCourses] = useState<CourseRow[]>([])
  const [selected, setSelected] = useState<AssignmentWithSubs | null>(null)
  const [loadingCourses, setLoadingCourses] = useState(true)
  const [loadingSubs, setLoadingSubs] = useState(false)
  const [grades, setGrades] = useState<Record<string, { score: string; feedback: string }>>({})
  const [saving, setSaving] = useState<string | null>(null)
  const [openSub, setOpenSub] = useState<string | null>(null)

  useEffect(() => {
    fetch("/api/admin/courses-with-assignments")
      .then(r => r.ok ? r.json() : [])
      .then(data => setCourses(data))
      .finally(() => setLoadingCourses(false))
  }, [])

  const loadAssignment = async (id: string) => {
    setLoadingSubs(true)
    try {
      const res = await fetch(`/api/assignments/${id}/submissions`)
      if (res.ok) {
        const data = await res.json()
        setSelected(data)
        const g: Record<string, { score: string; feedback: string }> = {}
        data.submissions.forEach((s: Submission) => { g[s.id] = { score: s.score?.toString() ?? "", feedback: s.feedback ?? "" } })
        setGrades(g)
      }
    } finally { setLoadingSubs(false) }
  }

  const handleGrade = async (subId: string) => {
    const g = grades[subId]
    if (!g) return
    setSaving(subId)
    try {
      const res = await fetch(`/api/submissions/${subId}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ score: parseFloat(g.score), feedback: g.feedback, status: "GRADED" }),
      })
      if (res.ok && selected) {
        const updated = await res.json()
        setSelected(prev => prev ? { ...prev, submissions: prev.submissions.map(s => s.id === subId ? { ...s, ...updated } : s) } : prev)
      }
    } finally { setSaving(null) }
  }

  return (
    <div className="p-6 lg:p-8 max-w-7xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
          <ClipboardList className="h-5 w-5 text-indigo-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Grading Queue</h1>
          <p className="text-sm text-slate-500 mt-0.5">Review and grade learner submissions</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-50">
            <p className="text-sm font-semibold text-slate-800">Courses & Assignments</p>
          </div>
          {loadingCourses ? (
            <div className="flex items-center justify-center py-10"><Loader2 className="h-5 w-5 text-indigo-400 animate-spin" /></div>
          ) : courses.length === 0 ? (
            <div className="py-10 text-center text-sm text-slate-400">No assignments created yet</div>
          ) : (
            <div className="divide-y divide-slate-50 overflow-y-auto max-h-[60vh]">
              {courses.map(c => (
                <div key={c.id}>
                  <div className="px-4 py-2.5 bg-slate-50">
                    <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide truncate">{c.title}</p>
                  </div>
                  {c.assignments.map(a => (
                    <button key={a.id} onClick={() => loadAssignment(a.id)}
                      className={`w-full px-4 py-3 text-left hover:bg-indigo-50 transition-colors flex items-center justify-between gap-2 ${selected?.assignment.id === a.id ? "bg-indigo-50" : ""}`}>
                      <span className="text-sm text-slate-700 truncate">{a.title}</span>
                      <span className="text-xs text-slate-400 flex-shrink-0">{a._count.submissions}</span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          {!selected ? (
            <div className="flex items-center justify-center h-full min-h-64 text-slate-400">
              <div className="text-center">
                <ClipboardList className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">Select an assignment to review submissions</p>
              </div>
            </div>
          ) : loadingSubs ? (
            <div className="flex items-center justify-center h-full min-h-64"><Loader2 className="h-6 w-6 text-indigo-400 animate-spin" /></div>
          ) : (
            <>
              <div className="px-5 py-4 border-b border-slate-50">
                <h2 className="text-sm font-semibold text-slate-900">{selected.assignment.title}</h2>
                <p className="text-xs text-slate-400 mt-0.5">{selected.submissions.length} submissions · Max score: {selected.assignment.maxScore}</p>
              </div>
              <div className="divide-y divide-slate-50 overflow-y-auto max-h-[60vh]">
                {selected.submissions.length === 0 ? (
                  <div className="py-10 text-center text-sm text-slate-400">No submissions yet</div>
                ) : selected.submissions.map(s => {
                  const g = grades[s.id] ?? { score: "", feedback: "" }
                  const isOpen = openSub === s.id
                  const initials = (s.user.name ?? "?").split(" ").map((n: string) => n[0]).join("").toUpperCase().slice(0, 2)
                  return (
                    <div key={s.id}>
                      <button onClick={() => setOpenSub(isOpen ? null : s.id)}
                        className="w-full px-5 py-3.5 flex items-center gap-3 text-left hover:bg-slate-50 transition-colors">
                        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0">{initials}</div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-800">{s.user.name ?? s.user.email}</p>
                          <p className="text-xs text-slate-400">{timeAgo(s.submittedAt)}</p>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {s.score !== null && (
                            <span className="flex items-center gap-0.5 text-xs font-semibold text-amber-600">
                              <Star className="h-3 w-3 text-amber-400" /> {s.score}/{selected.assignment.maxScore}
                            </span>
                          )}
                          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${STATUS_BADGE[s.status] ?? "bg-slate-100 text-slate-500"}`}>{s.status}</span>
                          {isOpen ? <ChevronUp className="h-3.5 w-3.5 text-slate-400" /> : <ChevronDown className="h-3.5 w-3.5 text-slate-400" />}
                        </div>
                      </button>

                      {isOpen && (
                        <div className="px-5 pb-5 bg-slate-50 space-y-4">
                          {s.content && (
                            <div>
                              <p className="text-xs font-semibold text-slate-600 mb-1.5">Submission</p>
                              <div className="bg-white rounded-xl border border-slate-100 p-3 text-sm text-slate-700 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">{s.content}</div>
                            </div>
                          )}
                          {s.fileUrl && (
                            <a href={s.fileUrl} target="_blank" rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-800">
                              <ExternalLink className="h-3.5 w-3.5" /> {s.fileName ?? "Attached file"}
                            </a>
                          )}
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label className="block text-xs font-semibold text-slate-600 mb-1">Score (/{selected.assignment.maxScore})</label>
                              <input type="number" min={0} max={selected.assignment.maxScore} value={g.score}
                                onChange={e => setGrades(prev => ({ ...prev, [s.id]: { ...prev[s.id], score: e.target.value } }))}
                                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white" />
                            </div>
                            <div>
                              <label className="block text-xs font-semibold text-slate-600 mb-1">Feedback (optional)</label>
                              <input value={g.feedback}
                                onChange={e => setGrades(prev => ({ ...prev, [s.id]: { ...prev[s.id], feedback: e.target.value } }))}
                                placeholder="Great work!"
                                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white" />
                            </div>
                          </div>
                          <button onClick={() => handleGrade(s.id)} disabled={saving === s.id || !g.score}
                            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition-colors">
                            {saving === s.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <><Check className="h-4 w-4" /> Save Grade</>}
                          </button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

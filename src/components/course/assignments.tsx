"use client"

import { useState, useEffect } from "react"
import { ClipboardList, ExternalLink, CheckCircle, Loader2, Plus, Star } from "lucide-react"

interface Submission { id: string; status: string; score: number | null; submittedAt: string }
interface Assignment {
  id: string; title: string; description: string | null; dueAt: string | null
  maxScore: number; isPublished: boolean; createdAt: string
  _count?: { submissions: number }; submissions?: Submission[]
}

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  SUBMITTED: { bg: "bg-indigo-50", text: "text-indigo-700", label: "Submitted" },
  GRADED:    { bg: "bg-emerald-50", text: "text-emerald-700", label: "Graded" },
  RETURNED:  { bg: "bg-amber-50", text: "text-amber-700", label: "Returned" },
}

function timeAgo(iso: string) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return "just now"
  const m = Math.floor(s / 60); if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function isOverdue(dueAt: string | null) {
  return dueAt ? new Date() > new Date(dueAt) : false
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
}

function SubmitForm({ assignmentId, onDone }: { assignmentId: string; onDone: () => void }) {
  const [content, setContent] = useState("")
  const [fileUrl, setFileUrl] = useState("")
  const [fileName, setFileName] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")

  const handleSubmit = async () => {
    if (!content.trim() && !fileUrl.trim()) { setError("Add text or a file link"); return }
    setSubmitting(true); setError("")
    try {
      const res = await fetch(`/api/assignments/${assignmentId}/submit`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, fileUrl, fileName }),
      })
      const d = await res.json()
      if (!res.ok) { setError(d.error ?? "Submit failed"); return }
      onDone()
    } finally { setSubmitting(false) }
  }

  return (
    <div className="space-y-4 mt-4 pt-4 border-t border-slate-100">
      <div>
        <label className="block text-xs font-medium text-slate-600 mb-1.5">Your answer</label>
        <textarea value={content} onChange={e => setContent(e.target.value)} rows={4}
          placeholder="Write your response here..."
          className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm text-slate-800 placeholder-slate-400 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1.5">File link (optional)</label>
          <input value={fileUrl} onChange={e => setFileUrl(e.target.value)}
            placeholder="https://drive.google.com/..."
            className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1.5">File name (optional)</label>
          <input value={fileName} onChange={e => setFileName(e.target.value)} placeholder="My Report.pdf"
            className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
        </div>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <button onClick={handleSubmit} disabled={submitting}
        className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition-colors">
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <><CheckCircle className="h-4 w-4" /> Submit</>}
      </button>
    </div>
  )
}

function AssignmentCard({ a, isModerator, onRefresh }: { a: Assignment; isModerator: boolean; onRefresh: () => void }) {
  const [open, setOpen] = useState(false)
  const submission = a.submissions?.[0] ?? null
  const overdue = isOverdue(a.dueAt)
  const st = submission ? STATUS_STYLES[submission.status] : null

  return (
    <div className="bg-white rounded-xl border border-slate-100 overflow-hidden shadow-sm">
      <button onClick={() => setOpen(!open)}
        className="w-full px-5 py-4 flex items-start gap-4 text-left hover:bg-slate-50 transition-colors">
        <div className={`mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${submission?.status === "GRADED" ? "bg-emerald-50" : "bg-indigo-50"}`}>
          <ClipboardList className={`h-4 w-4 ${submission?.status === "GRADED" ? "text-emerald-500" : "text-indigo-500"}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-semibold text-slate-900">{a.title}</p>
            <div className="flex items-center gap-2 flex-shrink-0">
              {st && <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${st.bg} ${st.text}`}>{st.label}</span>}
              {!submission && !isModerator && <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">Not submitted</span>}
              {isModerator && <span className="text-[10px] text-slate-400">{a._count?.submissions ?? 0} submissions</span>}
            </div>
          </div>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-slate-400">Max score: {a.maxScore}</span>
            {a.dueAt && <span className={`text-xs ${overdue ? "text-red-500" : "text-slate-400"}`}>Due {fmtDate(a.dueAt)}{overdue && " (overdue)"}</span>}
          </div>
          {submission?.status === "GRADED" && submission.score !== null && (
            <div className="flex items-center gap-1 mt-1">
              <Star className="h-3.5 w-3.5 text-amber-400" />
              <span className="text-xs font-semibold text-amber-600">{submission.score} / {a.maxScore}</span>
            </div>
          )}
        </div>
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-slate-50">
          {a.description && <p className="text-sm text-slate-600 mt-4 leading-relaxed whitespace-pre-wrap">{a.description}</p>}

          {!isModerator && (
            submission ? (
              <div className="mt-4 pt-4 border-t border-slate-100 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-slate-700">Your submission</p>
                  <span className="text-xs text-slate-400">Submitted {timeAgo(submission.submittedAt)}</span>
                </div>
                {submission.status === "GRADED" && submission.score !== null && (
                  <div className="bg-emerald-50 rounded-xl p-3 flex items-center gap-2">
                    <Star className="h-4 w-4 text-emerald-500" />
                    <span className="text-sm font-semibold text-emerald-700">Score: {submission.score} / {a.maxScore}</span>
                  </div>
                )}
              </div>
            ) : !overdue ? (
              <SubmitForm assignmentId={a.id} onDone={onRefresh} />
            ) : (
              <div className="mt-4 pt-4 border-t border-slate-100">
                <p className="text-sm text-red-500">The submission deadline has passed.</p>
              </div>
            )
          )}

          {isModerator && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <a href={`/assignments`} className="inline-flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-800 font-medium">
                <ExternalLink className="h-3.5 w-3.5" /> View & Grade Submissions
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function Assignments({ courseId }: { courseId: string }) {
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [isModerator, setIsModerator] = useState(false)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)

  const load = async () => {
    try {
      const res = await fetch(`/api/courses/${courseId}/assignments`)
      if (res.ok) {
        const data = await res.json()
        setAssignments(data.assignments ?? [])
        setIsModerator(data.isModerator ?? false)
      }
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [courseId])

  const handleCreate = async () => {
    const title = prompt("Assignment title:")
    if (!title?.trim()) return
    setCreating(true)
    try {
      const res = await fetch(`/api/courses/${courseId}/assignments`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim(), isPublished: true }),
      })
      if (res.ok) await load()
    } finally { setCreating(false) }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-indigo-500" />
          <h2 className="text-base font-semibold text-slate-800">
            Assignments
            {assignments.length > 0 && <span className="ml-2 text-xs font-normal text-slate-400">{assignments.length}</span>}
          </h2>
        </div>
        {isModerator && (
          <button onClick={handleCreate} disabled={creating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors">
            {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />} New Assignment
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="h-6 w-6 text-indigo-400 animate-spin" /></div>
      ) : assignments.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <ClipboardList className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">{isModerator ? "No assignments yet. Create one above." : "No assignments for this course yet."}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {assignments.map(a => <AssignmentCard key={a.id} a={a} isModerator={isModerator} onRefresh={load} />)}
        </div>
      )}
    </div>
  )
}

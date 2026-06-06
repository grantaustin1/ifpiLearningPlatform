"use client"

import { useState, useEffect, useRef } from "react"
import { Video, Plus, ExternalLink, Trash2, Loader2, X, Clock, Calendar, Users } from "lucide-react"

interface LiveSession {
  id: string; title: string; description: string | null; scheduledAt: string
  durationMins: number; meetingUrl: string | null; platform: string; maxCapacity: number | null
  isPublished: boolean; recordingUrl: string | null; createdAt: string
  course: { id: string; title: string } | null
  createdBy: { name: string | null }
}

const PLATFORM_LABELS: Record<string, string> = {
  zoom: "Zoom", meet: "Google Meet", teams: "Teams", custom: "Custom",
}
const PLATFORM_COLORS: Record<string, string> = {
  zoom: "bg-blue-50 text-blue-700", meet: "bg-emerald-50 text-emerald-700",
  teams: "bg-violet-50 text-violet-700", custom: "bg-slate-100 text-slate-600",
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
}

function isPast(iso: string) { return new Date(iso) < new Date() }

function CreateModal({ onClose, onCreate }: { onClose: () => void; onCreate: (s: LiveSession) => void }) {
  const [form, setForm] = useState({
    title: "", description: "", scheduledAt: "", durationMins: 60,
    meetingUrl: "", platform: "zoom", maxCapacity: "", isPublished: false,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const handleCreate = async () => {
    if (!form.title.trim() || !form.scheduledAt) { setError("Title and date are required"); return }
    setSaving(true); setError("")
    try {
      const res = await fetch("/api/live-sessions", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          durationMins: Number(form.durationMins),
          maxCapacity: form.maxCapacity ? Number(form.maxCapacity) : null,
        }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.error ?? "Create failed"); return }
      onCreate(data)
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-base font-semibold text-slate-900">New Live Session</h2>
          <button onClick={onClose}><X className="h-4 w-4 text-slate-400" /></button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Title *</label>
            <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              placeholder="e.g. Live Q&A Session"
              className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Date & Time *</label>
              <input type="datetime-local" value={form.scheduledAt} onChange={e => setForm(f => ({ ...f, scheduledAt: e.target.value }))}
                className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Duration (mins)</label>
              <input type="number" min={15} value={form.durationMins} onChange={e => setForm(f => ({ ...f, durationMins: parseInt(e.target.value) || 60 }))}
                className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Platform</label>
              <select value={form.platform} onChange={e => setForm(f => ({ ...f, platform: e.target.value }))}
                className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400">
                {Object.entries(PLATFORM_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Max capacity</label>
              <input type="number" min={1} value={form.maxCapacity} onChange={e => setForm(f => ({ ...f, maxCapacity: e.target.value }))}
                placeholder="Unlimited"
                className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Meeting URL</label>
            <input value={form.meetingUrl} onChange={e => setForm(f => ({ ...f, meetingUrl: e.target.value }))}
              placeholder="https://zoom.us/j/..."
              className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Description (optional)</label>
            <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={2}
              className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="publish" checked={form.isPublished} onChange={e => setForm(f => ({ ...f, isPublished: e.target.checked }))}
              className="rounded border-slate-300 text-indigo-600" />
            <label htmlFor="publish" className="text-sm text-slate-600">Publish immediately</label>
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="flex-1 py-2 rounded-xl border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-colors">Cancel</button>
            <button onClick={handleCreate} disabled={saving}
              className="flex-1 flex items-center justify-center gap-2 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition-colors">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Create Session"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function LiveSessionsPage() {
  const [sessions, setSessions] = useState<LiveSession[]>([])
  const [isModerator, setIsModerator] = useState(false)
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [filter, setFilter] = useState<"all" | "upcoming" | "past">("upcoming")

  const load = async () => {
    try {
      const res = await fetch("/api/live-sessions")
      if (res.ok) {
        const data = await res.json()
        setSessions(data.sessions ?? [])
        setIsModerator(data.isModerator ?? false)
      }
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this live session?")) return
    setDeleting(id)
    try {
      await fetch(`/api/live-sessions/${id}`, { method: "DELETE" })
      setSessions(prev => prev.filter(s => s.id !== id))
    } finally { setDeleting(null) }
  }

  const filtered = sessions.filter(s => {
    if (filter === "upcoming") return !isPast(s.scheduledAt)
    if (filter === "past") return isPast(s.scheduledAt)
    return true
  })

  return (
    <div className="p-6 lg:p-8 max-w-5xl">
      {showCreate && <CreateModal onClose={() => setShowCreate(false)} onCreate={s => { setSessions(prev => [s, ...prev].sort((a, b) => new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime())); setShowCreate(false) }} />}

      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
            <Video className="h-5 w-5 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Live Sessions</h1>
            <p className="text-sm text-slate-500 mt-0.5">Schedule and manage virtual classes</p>
          </div>
        </div>
        {isModerator && (
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors">
            <Plus className="h-4 w-4" /> New Session
          </button>
        )}
      </div>

      <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5 w-fit mb-6">
        {(["upcoming", "past", "all"] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all capitalize ${filter === f ? "bg-white shadow-sm text-slate-900" : "text-slate-500 hover:text-slate-700"}`}>
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16"><Loader2 className="h-6 w-6 text-indigo-400 animate-spin" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <Video className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">{filter === "upcoming" ? "No upcoming sessions. Create one above!" : "No sessions found."}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(s => {
            const past = isPast(s.scheduledAt)
            return (
              <div key={s.id} className={`bg-white rounded-2xl border shadow-sm p-5 ${past ? "border-slate-100 opacity-80" : "border-slate-100"}`}>
                <div className="flex items-start gap-4">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${past ? "bg-slate-100" : "bg-indigo-50"}`}>
                    <Video className={`h-5 w-5 ${past ? "text-slate-400" : "text-indigo-500"}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-slate-900">{s.title}</h3>
                        {s.course && <p className="text-xs text-slate-500 mt-0.5">Course: {s.course.title}</p>}
                        {s.description && <p className="text-xs text-slate-500 mt-1 line-clamp-2">{s.description}</p>}
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${PLATFORM_COLORS[s.platform] ?? "bg-slate-100 text-slate-500"}`}>
                          {PLATFORM_LABELS[s.platform] ?? s.platform}
                        </span>
                        {!s.isPublished && <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">Draft</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                      <span className="flex items-center gap-1"><Calendar className="h-3.5 w-3.5" /> {fmtDate(s.scheduledAt)}</span>
                      <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {s.durationMins} min</span>
                      {s.maxCapacity && <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> Max {s.maxCapacity}</span>}
                    </div>
                    <div className="flex items-center gap-3 mt-3">
                      {s.meetingUrl && !past && (
                        <a href={s.meetingUrl} target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-800">
                          <ExternalLink className="h-3.5 w-3.5" /> Join Session
                        </a>
                      )}
                      {s.recordingUrl && (
                        <a href={s.recordingUrl} target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-800">
                          <ExternalLink className="h-3.5 w-3.5" /> View Recording
                        </a>
                      )}
                      {isModerator && (
                        <button onClick={() => handleDelete(s.id)} disabled={deleting === s.id}
                          className="ml-auto flex items-center gap-1 text-xs text-slate-400 hover:text-red-500 transition-colors">
                          {deleting === s.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />} Delete
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

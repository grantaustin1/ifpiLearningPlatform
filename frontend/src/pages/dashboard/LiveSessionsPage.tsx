import { useEffect, useMemo, useState } from 'react'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { toast } from 'sonner'
import {
  Video, Calendar, Clock, Users, Link2, Plus, X, Check, Download,
  UserCheck, UserX, ExternalLink, Trash2, Loader2,
} from 'lucide-react'

interface LiveSession {
  id: number
  title: string
  description?: string | null
  meeting_url: string
  start_at: string
  duration_minutes: number
  host_name?: string | null
  cohort?: string | null
  max_attendees?: number | null
  course_id?: number | null
  rsvp_count: number
  attendance_count: number
  my_rsvp_status?: 'RSVP' | 'CANCELLED' | 'ATTENDED' | 'NO_SHOW' | null
  rsvps?: {
    user_id: number
    status: string
    rsvped_at: string
    attendance_marked_at: string | null
  }[]
}

function fmtDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function relTime(iso: string): string {
  const d = new Date(iso).getTime() - Date.now()
  const abs = Math.abs(d)
  const min = Math.floor(abs / 60_000)
  const hr = Math.floor(min / 60)
  const day = Math.floor(hr / 24)
  const sign = d >= 0 ? 'in ' : ''
  const suffix = d >= 0 ? '' : ' ago'
  if (day >= 1) return `${sign}${day}d${suffix}`
  if (hr >= 1) return `${sign}${hr}h${suffix}`
  return `${sign}${min}m${suffix}`
}

export default function LiveSessionsPage() {
  const { hasRole } = useAuth()
  const isAdmin = hasRole('ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR')
  const [sessions, setSessions] = useState<LiveSession[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [detailId, setDetailId] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const endpoint = isAdmin ? '/live-sessions?upcoming=true' : '/live-sessions/upcoming'
      const r = await api.get(endpoint)
      setSessions(r.data.sessions || [])
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to load sessions')
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const toggleRsvp = async (s: LiveSession) => {
    try {
      const r = await api.post(`/live-sessions/${s.id}/rsvp`)
      toast.success(r.data.status === 'RSVP' ? 'You\u2019re RSVP\u2019d' : 'RSVP cancelled')
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed')
    }
  }

  const downloadIcs = async (s: LiveSession) => {
    try {
      const r = await api.get(`/live-sessions/${s.id}/ics`, { responseType: 'blob' })
      const blob = new Blob([r.data], { type: 'text/calendar' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `live-session-${s.id}.ics`
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      toast.error('Download failed')
    }
  }

  const deleteSession = async (id: number) => {
    if (!window.confirm('Delete this session?')) return
    try {
      await api.delete(`/live-sessions/${id}`)
      toast.success('Session removed')
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Delete failed')
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6" data-testid="live-sessions-page">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2"><Video className="h-6 w-6 text-indigo-600" /> Live sessions</h1>
          <p className="text-sm text-slate-500 mt-1">Scheduled cohort sessions on your preferred meeting platform.</p>
        </div>
        {isAdmin && (
          <button onClick={() => setShowCreate(true)} data-testid="new-session-btn"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
            <Plus className="h-4 w-4" /> Schedule session
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-indigo-600" /></div>
      ) : sessions.length === 0 ? (
        <div className="text-center py-16 text-slate-400 border-2 border-dashed border-slate-200 rounded-2xl" data-testid="live-sessions-empty">
          <Calendar className="h-10 w-10 mx-auto mb-3 text-slate-300" />
          <p className="text-sm">No upcoming live sessions.</p>
          {isAdmin && (
            <button onClick={() => setShowCreate(true)} className="text-indigo-600 text-sm font-medium mt-2">
              Schedule your first session →
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="sessions-grid">
          {sessions.map(s => {
            const rsvped = s.my_rsvp_status === 'RSVP'
            return (
              <div key={s.id} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm" data-testid={`session-card-${s.id}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-slate-900 truncate">{s.title}</h3>
                    {s.host_name && <p className="text-xs text-slate-500 mt-0.5">Hosted by {s.host_name}</p>}
                  </div>
                  {isAdmin && (
                    <button onClick={() => deleteSession(s.id)} className="text-slate-300 hover:text-red-500" data-testid={`del-${s.id}`}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
                {s.description && <p className="text-sm text-slate-600 mt-2 line-clamp-2">{s.description}</p>}
                <div className="flex flex-wrap items-center gap-4 mt-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1"><Calendar className="h-3.5 w-3.5" /> {fmtDate(s.start_at)}</span>
                  <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {s.duration_minutes}m · {relTime(s.start_at)}</span>
                  <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {s.rsvp_count}{s.max_attendees ? `/${s.max_attendees}` : ''} RSVP</span>
                  {s.cohort && <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">{s.cohort}</span>}
                </div>
                <div className="flex flex-wrap items-center gap-2 mt-4">
                  <a href={s.meeting_url} target="_blank" rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-medium bg-slate-900 hover:bg-slate-800 text-white px-3 py-1.5 rounded-lg"
                    data-testid={`join-${s.id}`}>
                    <ExternalLink className="h-3.5 w-3.5" /> Join
                  </a>
                  {!isAdmin && (
                    <button onClick={() => toggleRsvp(s)} data-testid={`rsvp-${s.id}`}
                      className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${rsvped
                        ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                        : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'}`}>
                      {rsvped ? <><Check className="h-3.5 w-3.5" /> RSVP&apos;d</> : <><UserCheck className="h-3.5 w-3.5" /> RSVP</>}
                    </button>
                  )}
                  <button onClick={() => downloadIcs(s)} data-testid={`ics-${s.id}`}
                    className="inline-flex items-center gap-1.5 text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg">
                    <Download className="h-3.5 w-3.5" /> .ics
                  </button>
                  {isAdmin && (
                    <button onClick={() => setDetailId(s.id)} data-testid={`manage-${s.id}`}
                      className="inline-flex items-center gap-1.5 text-xs font-medium bg-white border border-slate-200 hover:border-slate-300 text-slate-700 px-3 py-1.5 rounded-lg">
                      <Users className="h-3.5 w-3.5" /> Attendance
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {showCreate && <CreateSessionModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load() }} />}
      {detailId !== null && <AttendanceModal sessionId={detailId} onClose={() => { setDetailId(null); load() }} />}
    </div>
  )
}

// ── Create modal ────────────────────────────────────────────────────
function CreateSessionModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [meetingUrl, setMeetingUrl] = useState('')
  const [startAt, setStartAt] = useState('')
  const [duration, setDuration] = useState(60)
  const [cohort, setCohort] = useState('')
  const [hostName, setHostName] = useState('')
  const [maxAttendees, setMaxAttendees] = useState<number | ''>('')
  const [saving, setSaving] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api.post('/live-sessions', {
        title,
        description: description || null,
        meeting_url: meetingUrl,
        start_at: new Date(startAt).toISOString(),
        duration_minutes: duration,
        cohort: cohort || null,
        host_name: hostName || null,
        max_attendees: maxAttendees === '' ? null : maxAttendees,
      })
      toast.success('Session scheduled')
      onCreated()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Create failed')
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" data-testid="create-session-modal">
      <div className="bg-white rounded-2xl w-full max-w-lg shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900">Schedule live session</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X className="h-4 w-4" /></button>
        </div>
        <form onSubmit={submit} className="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <label className="text-xs font-medium text-slate-700">Title *</label>
            <input value={title} onChange={e => setTitle(e.target.value)} required data-testid="input-title"
              className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700">Description</label>
            <textarea value={description} onChange={e => setDescription(e.target.value)} rows={2}
              className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700 flex items-center gap-1"><Link2 className="h-3 w-3" /> Meeting URL *</label>
            <input type="url" value={meetingUrl} onChange={e => setMeetingUrl(e.target.value)} required
              placeholder="https://zoom.us/j/..." data-testid="input-meeting-url"
              className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-700">Start *</label>
              <input type="datetime-local" value={startAt} onChange={e => setStartAt(e.target.value)} required
                data-testid="input-start-at"
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700">Duration (min)</label>
              <input type="number" min={5} max={480} value={duration} onChange={e => setDuration(parseInt(e.target.value) || 60)}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-700">Host name</label>
              <input value={hostName} onChange={e => setHostName(e.target.value)}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700">Cohort (optional)</label>
              <input value={cohort} onChange={e => setCohort(e.target.value)} placeholder="e.g. 2026-A"
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700">Max attendees (optional)</label>
            <input type="number" min={1} value={maxAttendees} onChange={e => setMaxAttendees(e.target.value === '' ? '' : parseInt(e.target.value))}
              className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="text-sm text-slate-600 px-4 py-2 rounded-lg hover:bg-slate-50">Cancel</button>
            <button type="submit" disabled={saving} data-testid="submit-session"
              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Schedule
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Attendance modal ────────────────────────────────────────────────
function AttendanceModal({ sessionId, onClose }: { sessionId: number; onClose: () => void }) {
  const [session, setSession] = useState<LiveSession | null>(null)
  const [users, setUsers] = useState<Record<number, { name: string; email: string }>>({})
  const [saving, setSaving] = useState(false)

  const load = async () => {
    const r = await api.get(`/live-sessions/${sessionId}`)
    setSession(r.data)
    // Bulk-fetch user names
    const ids: number[] = (r.data.rsvps || []).map((x: any) => x.user_id)
    if (ids.length > 0) {
      try {
        const u = await api.get('/admin/users', { params: { user_ids: ids.join(',') } })
        const map: Record<number, { name: string; email: string }> = {}
        for (const row of (u.data || [])) map[row.id] = { name: row.name || row.email, email: row.email }
        setUsers(map)
      } catch { /* fallback: show IDs */ }
    }
  }
  useEffect(() => { load() }, [sessionId])

  const mark = async (userId: number, status: 'ATTENDED' | 'NO_SHOW') => {
    setSaving(true)
    try {
      await api.post(`/live-sessions/${sessionId}/mark-attendance`, {
        user_ids: [userId], status,
      })
      toast.success('Attendance updated')
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed')
    } finally { setSaving(false) }
  }

  const rsvps = useMemo(() => {
    return (session?.rsvps || []).filter(r => r.status !== 'CANCELLED')
  }, [session])

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" data-testid="attendance-modal">
      <div className="bg-white rounded-2xl w-full max-w-lg shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <div>
            <h2 className="font-semibold text-slate-900">Attendance</h2>
            {session && <p className="text-xs text-slate-500 mt-0.5">{session.title}</p>}
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" data-testid="close-attendance"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5 max-h-[60vh] overflow-y-auto">
          {rsvps.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-8">No RSVPs yet.</p>
          ) : (
            <ul className="space-y-2" data-testid="attendance-list">
              {rsvps.map(r => (
                <li key={r.user_id} className="flex items-center justify-between p-3 rounded-lg border border-slate-100" data-testid={`attendee-${r.user_id}`}>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate">{users[r.user_id]?.name || `User #${r.user_id}`}</p>
                    <p className="text-xs text-slate-400">{r.status} · RSVP&apos;d {fmtDate(r.rsvped_at)}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button disabled={saving} onClick={() => mark(r.user_id, 'ATTENDED')}
                      className={`p-1.5 rounded-md ${r.status === 'ATTENDED' ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-50 text-slate-400 hover:text-emerald-500'}`}
                      data-testid={`mark-attend-${r.user_id}`} title="Attended">
                      <UserCheck className="h-4 w-4" />
                    </button>
                    <button disabled={saving} onClick={() => mark(r.user_id, 'NO_SHOW')}
                      className={`p-1.5 rounded-md ${r.status === 'NO_SHOW' ? 'bg-red-100 text-red-600' : 'bg-slate-50 text-slate-400 hover:text-red-500'}`}
                      data-testid={`mark-noshow-${r.user_id}`} title="No-show">
                      <UserX className="h-4 w-4" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

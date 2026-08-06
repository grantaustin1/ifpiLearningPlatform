import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { toast } from 'sonner'
import {
  Video, Calendar, Clock, Users, Plus, XCircle, Check, Download,
  ExternalLink, Trash2, Loader2, RotateCcw, UserCheck,
} from 'lucide-react'
import { useConfirm } from 'components/ConfirmDialog'
import { SubscriptionModal, SubscriptionKindPicker } from './live-sessions/SubscriptionModal'
import { CreateSessionModal } from './live-sessions/CreateSessionModal'
import { AttendanceModal } from './live-sessions/AttendanceModal'

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
  recurrence_rule?: string | null
  parent_series_id?: number | null
  cancelled_at?: string | null
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
  const confirm = useConfirm()
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

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load() }, [])

  const toggleRsvp = async (s: LiveSession, allInSeries = false) => {
    try {
      const path = allInSeries
        ? `/live-sessions/${s.id}/rsvp?series=true`
        : `/live-sessions/${s.id}/rsvp`
      const r = await api.post(path)
      if (allInSeries) {
        toast.success(r.data.status === 'RSVP'
          ? `You\u2019re RSVP\u2019d for the full series (${r.data.series_count} sessions)`
          : `Series RSVP cancelled (${r.data.series_count} sessions)`)
      } else {
        toast.success(r.data.status === 'RSVP' ? 'You\u2019re RSVP\u2019d' : 'RSVP cancelled')
      }
      // Iter 29 — Cohort auto-enrol from RSVP: surface the enrolment
      // as a distinct celebratory toast so the learner knows the
      // course is now on their dashboard.
      if (r.data.auto_enrolled && r.data.course_id) {
        toast.success('\u2728 You\u2019ve also been enrolled in the course', {
          action: {
            label: 'Open',
            onClick: () => { window.location.href = `/learn/${r.data.course_id}` },
          },
          duration: 6000,
        })
      }
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed')
    }
  }

  const [subscriptionUrl, setSubscriptionUrl] = useState<string | null>(null)
  const [subscriptionKind, setSubscriptionKind] = useState<'admin' | 'learner' | 'my_rsvps'>('admin')
  const [showKindPicker, setShowKindPicker] = useState(false)

  const getSubscriptionUrl = async (kind: 'admin' | 'learner' | 'my_rsvps') => {
    try {
      const r = await api.post(`/live-sessions/subscribe-url?kind=${kind}`)
      const backend = (import.meta as any).env?.VITE_BACKEND_URL || process.env.REACT_APP_BACKEND_URL || window.location.origin
      const fullUrl = `${backend}${r.data.path}`
      setSubscriptionKind(kind)
      setSubscriptionUrl(fullUrl)
      setShowKindPicker(false)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed')
    }
  }

  const onSubscribeClick = () => {
    // Admins go straight to the admin feed; learners choose between
    // "everything in my cohort" and "only sessions I RSVP'd to".
    if (isAdmin) return getSubscriptionUrl('admin')
    setShowKindPicker(true)
  }

  const rotateSubscriptionSecret = async () => {
    if (!(await confirm({
      title: 'Rotate subscription secret?',
      description: 'All existing calendar subscription URLs for your organisation will stop working. Users will need to re-copy their fresh URL.',
      confirmLabel: 'Rotate',
      variant: 'danger',
    }))) return
    try {
      const r = await api.post('/live-sessions/subscribe-url/rotate')
      toast.success(`Secret rotated to v${r.data.new_version} — old URLs revoked`)
      // Refresh the current modal's URL to the new one
      if (subscriptionUrl) await getSubscriptionUrl(subscriptionKind)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Rotation failed')
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

  const cancelOccurrence = async (s: LiveSession) => {
    try {
      const url = s.cancelled_at
        ? `/live-sessions/${s.id}/uncancel`
        : `/live-sessions/${s.id}/cancel`
      await api.post(url)
      toast.success(s.cancelled_at ? 'Occurrence restored' : 'Occurrence cancelled')
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed')
    }
  }

  const deleteSession = async (s: LiveSession) => {
    const inSeries = s.recurrence_rule || s.parent_series_id
    let cascade = false
    if (inSeries) {
      const choice = await confirm({
        title: 'Delete recurring session?',
        description: 'This session is part of a recurring series. Delete the WHOLE series (all future occurrences) or ONLY this occurrence?',
        confirmLabel: 'Delete whole series',
        cancelLabel: 'Delete this occurrence',
        variant: 'danger',
      })
      cascade = choice
    } else if (!(await confirm({
      title: 'Delete this session?',
      description: 'The session and any RSVPs will be removed. This cannot be undone.',
      variant: 'danger',
      confirmLabel: 'Delete',
    }))) {
      return
    }
    try {
      const url = cascade
        ? `/live-sessions/${s.id}?cascade_series=true`
        : `/live-sessions/${s.id}`
      await api.delete(url)
      toast.success(cascade ? 'Series deleted' : 'Session removed')
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
        <button onClick={onSubscribeClick}
          data-testid="subscribe-calendar-btn"
          className="inline-flex items-center gap-2 bg-white border border-slate-200 hover:border-slate-300 text-slate-700 text-sm font-medium px-4 py-2 rounded-lg">
          <Calendar className="h-4 w-4" /> Subscribe to calendar
        </button>
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
                    <div className="flex items-center gap-2">
                      <h3 className={`font-semibold truncate ${s.cancelled_at ? 'text-slate-400 line-through' : 'text-slate-900'}`}>{s.title}</h3>
                      {(s.recurrence_rule || s.parent_series_id) && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600" data-testid={`series-badge-${s.id}`}>Series</span>
                      )}
                      {s.cancelled_at && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-red-50 text-red-600" data-testid={`cancelled-badge-${s.id}`}>Cancelled</span>
                      )}
                    </div>
                    {s.host_name && <p className="text-xs text-slate-500 mt-0.5">Hosted by {s.host_name}</p>}
                  </div>
                  {isAdmin && (
                    <div className="flex items-center gap-1">
                      <button onClick={() => cancelOccurrence(s)}
                        title={s.cancelled_at ? 'Restore occurrence' : 'Cancel this occurrence'}
                        className={`p-1 rounded ${s.cancelled_at ? 'text-emerald-500 hover:bg-emerald-50' : 'text-slate-300 hover:text-amber-500'}`}
                        data-testid={`cancel-${s.id}`}>
                        {s.cancelled_at ? <RotateCcw className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                      </button>
                      <button onClick={() => deleteSession(s)} className="text-slate-300 hover:text-red-500 p-1" data-testid={`del-${s.id}`}>
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
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
                    <>
                      <button onClick={() => toggleRsvp(s)} data-testid={`rsvp-${s.id}`}
                        className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${rsvped
                          ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                          : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'}`}>
                        {rsvped ? <><Check className="h-3.5 w-3.5" /> RSVP&apos;d</> : <><UserCheck className="h-3.5 w-3.5" /> RSVP</>}
                      </button>
                      {(s.recurrence_rule || s.parent_series_id) && (
                        <button onClick={() => toggleRsvp(s, true)} data-testid={`rsvp-series-${s.id}`}
                          className="inline-flex items-center gap-1.5 text-xs font-medium bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 px-3 py-1.5 rounded-lg">
                          <Calendar className="h-3.5 w-3.5" /> RSVP whole series
                        </button>
                      )}
                    </>
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
      {showKindPicker && (
        <SubscriptionKindPicker
          onPick={getSubscriptionUrl}
          onClose={() => setShowKindPicker(false)}
        />
      )}
      {subscriptionUrl && (
        <SubscriptionModal
          url={subscriptionUrl}
          kind={subscriptionKind}
          isAdmin={isAdmin}
          onClose={() => setSubscriptionUrl(null)}
          onRotate={rotateSubscriptionSecret}
        />
      )}
    </div>
  )
}


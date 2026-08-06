import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { X, UserCheck, UserX } from 'lucide-react'
import { api } from 'lib/api'
import { useConfirm } from 'components/ConfirmDialog'

/**
 * AttendanceModal — Instructor marks each RSVP'd learner ATTENDED or
 * NO_SHOW. In iter-27 the backend auto-issues an attendance certificate
 * on ATTENDED, so this modal's "checkmark" click IS the trigger for
 * the branded PDF being generated. Extracted from LiveSessionsPage.tsx.
 */
interface Rsvp {
  user_id: number
  status: string
  rsvped_at: string
  attendance_marked_at: string | null
}

interface SessionDetail {
  id: number
  title: string
  rsvps?: Rsvp[]
}

function fmtDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function AttendanceModal({ sessionId, onClose }: {
  sessionId: number
  onClose: () => void
}) {
  const confirm = useConfirm()
  const [session, setSession] = useState<SessionDetail | null>(null)
  const [users, setUsers] = useState<Record<number, { name: string; email: string }>>({})
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    const r = await api.get(`/live-sessions/${sessionId}`)
    setSession(r.data)
    const ids: number[] = (r.data.rsvps || []).map((x: Rsvp) => x.user_id)
    if (ids.length > 0) {
      try {
        const u = await api.get('/admin/users', { params: { user_ids: ids.join(',') } })
        const map: Record<number, { name: string; email: string }> = {}
        for (const row of (u.data || [])) map[row.id] = { name: row.name || row.email, email: row.email }
        setUsers(map)
      } catch { /* fallback: show IDs */ }
    }
  }, [sessionId])
  useEffect(() => { load() }, [load])

  const mark = async (userId: number, status: 'ATTENDED' | 'NO_SHOW') => {
    setSaving(true)
    try {
      const r = await api.post(`/live-sessions/${sessionId}/mark-attendance`, {
        user_ids: [userId], status,
      })
      // Iter 27 — Attendance cert auto-issued on ATTENDED
      const issued = r.data?.attendance_certs_issued ?? 0
      if (status === 'ATTENDED' && issued > 0) {
        toast.success('Attendance recorded · certificate issued')
      } else {
        toast.success('Attendance updated')
      }
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed')
    } finally { setSaving(false) }
  }

  // Iter 28 — Bulk "Mark all as ATTENDED" quick action. Skips learners
  // already marked ATTENDED so idempotent re-clicks don't re-fire.
  const markAllAttended = async () => {
    const targets = rsvps.filter(r => r.status !== 'ATTENDED').map(r => r.user_id)
    if (targets.length === 0) {
      toast.info('Everyone is already marked ATTENDED')
      return
    }
    if (!(await confirm({
      title: 'Mark everyone as ATTENDED?',
      description: `${targets.length} learner${targets.length === 1 ? '' : 's'} will be marked ATTENDED and receive their attendance certificate by email.`,
      confirmLabel: 'Mark all',
    }))) return
    setSaving(true)
    try {
      const r = await api.post(`/live-sessions/${sessionId}/mark-attendance`, {
        user_ids: targets, status: 'ATTENDED',
      })
      const issued = r.data?.attendance_certs_issued ?? 0
      toast.success(
        issued > 0
          ? `${r.data.marked} marked · ${issued} certificate${issued === 1 ? '' : 's'} issued`
          : `${r.data.marked} marked as ATTENDED`
      )
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Bulk mark failed')
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
        {rsvps.length > 0 && (
          <div className="px-5 pt-3 pb-2 border-b border-slate-100 flex justify-end">
            <button
              onClick={markAllAttended}
              disabled={saving}
              data-testid="mark-all-attended-btn"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 px-3 py-1.5 rounded-lg disabled:opacity-50"
              title="Mark every RSVP'd learner as ATTENDED (auto-issues certificates)"
            >
              <UserCheck className="h-3.5 w-3.5" /> Mark all as ATTENDED
            </button>
          </div>
        )}
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

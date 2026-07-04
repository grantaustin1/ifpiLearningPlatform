import { useState } from 'react'
import { toast } from 'sonner'
import { X, Plus, Link2, Loader2 } from 'lucide-react'
import { api } from 'lib/api'

/**
 * CreateSessionModal — schedule a new live session (optionally
 * recurring). Extracted from LiveSessionsPage.tsx in iter-27.
 */
export function CreateSessionModal({ onClose, onCreated }: {
  onClose: () => void
  onCreated: () => void
}) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [meetingUrl, setMeetingUrl] = useState('')
  const [startAt, setStartAt] = useState('')
  const [duration, setDuration] = useState(60)
  const [cohort, setCohort] = useState('')
  const [hostName, setHostName] = useState('')
  const [maxAttendees, setMaxAttendees] = useState<number | ''>('')
  const [recurrenceType, setRecurrenceType] = useState<'none' | 'weekly' | 'daily' | 'biweekly' | 'custom'>('none')
  const [recurrenceCount, setRecurrenceCount] = useState(4)
  const [customRrule, setCustomRrule] = useState('')
  const [saving, setSaving] = useState(false)

  const buildRrule = (): string | null => {
    if (recurrenceType === 'none') return null
    if (recurrenceType === 'custom') return customRrule.trim() || null
    if (recurrenceType === 'weekly') return `FREQ=WEEKLY;COUNT=${recurrenceCount}`
    if (recurrenceType === 'biweekly') return `FREQ=WEEKLY;INTERVAL=2;COUNT=${recurrenceCount}`
    if (recurrenceType === 'daily') return `FREQ=DAILY;COUNT=${recurrenceCount}`
    return null
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const rrule = buildRrule()
      const r = await api.post('/live-sessions', {
        title,
        description: description || null,
        meeting_url: meetingUrl,
        start_at: new Date(startAt).toISOString(),
        duration_minutes: duration,
        cohort: cohort || null,
        host_name: hostName || null,
        max_attendees: maxAttendees === '' ? null : maxAttendees,
        recurrence_rule: rrule,
      })
      const created = r.data.series_instances_created || 0
      toast.success(created > 0
        ? `Session scheduled with ${created + 1} occurrences`
        : 'Session scheduled')
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

          <div className="pt-3 border-t border-slate-100">
            <label className="text-xs font-medium text-slate-700 block mb-2">Repeat</label>
            <div className="grid grid-cols-2 gap-3">
              <select value={recurrenceType} onChange={e => setRecurrenceType(e.target.value as typeof recurrenceType)}
                data-testid="recurrence-type"
                className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white">
                <option value="none">Does not repeat</option>
                <option value="weekly">Weekly</option>
                <option value="biweekly">Every 2 weeks</option>
                <option value="daily">Daily</option>
                <option value="custom">Custom RRULE</option>
              </select>
              {recurrenceType !== 'none' && recurrenceType !== 'custom' && (
                <div>
                  <label className="text-xs text-slate-500">Occurrences (max 26)</label>
                  <input type="number" min={2} max={26} value={recurrenceCount}
                    onChange={e => setRecurrenceCount(Math.max(2, Math.min(26, parseInt(e.target.value) || 2)))}
                    data-testid="recurrence-count"
                    className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm" />
                </div>
              )}
            </div>
            {recurrenceType === 'custom' && (
              <input value={customRrule} onChange={e => setCustomRrule(e.target.value)}
                placeholder="FREQ=WEEKLY;COUNT=8"
                data-testid="recurrence-custom-rrule"
                className="mt-2 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono" />
            )}
            {recurrenceType !== 'none' && (
              <p className="text-[11px] text-slate-400 mt-2">
                All occurrences will be created as separate sessions. Delete the first session with &ldquo;Delete series&rdquo; to remove them all at once.
              </p>
            )}
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

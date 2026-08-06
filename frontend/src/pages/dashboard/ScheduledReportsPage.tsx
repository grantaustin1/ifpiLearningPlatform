/**
 * Iter 30p — Scheduled Reports admin UI.
 *
 * CRUD list for per-admin schedulable analytics emails. Complements the
 * built-in Monday cohort digest (which is always-on for the org).
 */
import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { Mail, Plus, Trash2, Play, Loader2, ToggleRight } from 'lucide-react'
import { toast } from 'sonner'
import { useConfirm } from 'components/ConfirmDialog'

type Report = {
  id: number
  report_kind: string
  cadence: string
  recipient_emails: string[]
  is_active: boolean
  last_run_at: string | null
  next_run_at: string
}

const KINDS = [
  { key: 'members_needing_action', label: 'Members needing action' },
  { key: 'cohort_progress', label: 'Cohort progress' },
  { key: 'certificate_issuance', label: 'Certificate issuance (30d)' },
  { key: 'enrollment_summary', label: 'Enrollment summary' },
]
const CADENCES = ['daily', 'weekly', 'monthly']

export default function ScheduledReportsPage() {
  const confirm = useConfirm()
  const [items, setItems] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [kind, setKind] = useState('members_needing_action')
  const [cadence, setCadence] = useState('weekly')
  const [emails, setEmails] = useState('')
  const [busy, setBusy] = useState(false)

  const load = async () => {
    setLoading(true)
    const r = await api.get('/admin/scheduled-reports')
    setItems(r.data.items)
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const create = async () => {
    const recipients = emails.split(',').map(e => e.trim()).filter(Boolean)
    if (recipients.length === 0) return toast.error('At least one recipient required')
    setBusy(true)
    try {
      await api.post('/admin/scheduled-reports', {
        report_kind: kind, cadence, recipient_emails: recipients,
      })
      setEmails('')
      await load()
      toast.success('Schedule created')
    } catch (e: any) {
      const msg = e?.response?.data?.detail
      toast.error(Array.isArray(msg) ? msg[0]?.msg : (msg || 'Create failed'))
    } finally { setBusy(false) }
  }

  const runNow = async (id: number) => {
    try {
      await api.post(`/admin/scheduled-reports/${id}/run-now`)
      toast.success('Report queued — check your inbox shortly')
      await load()
    } catch { toast.error('Run failed') }
  }

  const toggle = async (r: Report) => {
    try {
      await api.put(`/admin/scheduled-reports/${r.id}`, {
        report_kind: r.report_kind, cadence: r.cadence,
        recipient_emails: r.recipient_emails, is_active: !r.is_active,
      })
      await load()
    } catch { toast.error('Update failed') }
  }

  const remove = async (id: number) => {
    if (!(await confirm({
      title: 'Delete scheduled report?',
      description: 'Recipients will stop receiving future emails immediately.',
      confirmLabel: 'Delete', variant: 'danger',
    }))) return
    try {
      await api.delete(`/admin/scheduled-reports/${id}`)
      await load()
      toast.success('Deleted')
    } catch { toast.error('Delete failed') }
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6" data-testid="scheduled-reports-page">
      <header className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center">
          <Mail className="h-5 w-5 text-indigo-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Scheduled reports</h1>
          <p className="text-sm text-slate-500">
            Emails on a cadence — beyond the built-in Monday cohort digest.
          </p>
        </div>
      </header>

      <section className="bg-white border border-slate-200 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-slate-800 mb-3">Add a schedule</h2>
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
          <select value={kind} onChange={e => setKind(e.target.value)}
                  data-testid="report-kind-select"
                  className="px-3 py-2 border border-slate-300 rounded-lg text-sm">
            {KINDS.map(k => <option key={k.key} value={k.key}>{k.label}</option>)}
          </select>
          <select value={cadence} onChange={e => setCadence(e.target.value)}
                  data-testid="report-cadence-select"
                  className="px-3 py-2 border border-slate-300 rounded-lg text-sm">
            {CADENCES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <input value={emails} onChange={e => setEmails(e.target.value)}
                 placeholder="recipient@…, another@…"
                 data-testid="report-emails-input"
                 className="md:col-span-2 px-3 py-2 border border-slate-300 rounded-lg text-sm" />
        </div>
        <button onClick={create} disabled={busy || !emails.trim()}
                data-testid="report-create-btn"
                className="mt-3 inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-sm font-semibold px-4 py-2 rounded-lg">
          <Plus className="h-4 w-4" /> Create schedule
        </button>
      </section>

      <section className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-800">Active schedules</h2>
        </div>
        {loading ? (
          <div className="py-10 text-center"><Loader2 className="h-5 w-5 animate-spin text-slate-400 mx-auto" /></div>
        ) : items.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-400" data-testid="reports-empty">
            No custom schedules yet.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100" data-testid="reports-list">
            {items.map(r => (
              <li key={r.id} className="flex items-center gap-4 px-5 py-3" data-testid={`report-row-${r.id}`}>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800">
                    {KINDS.find(k => k.key === r.report_kind)?.label || r.report_kind}
                    <span className="ml-2 text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 uppercase">{r.cadence}</span>
                    {!r.is_active && (
                      <span className="ml-2 text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-200 text-slate-500 uppercase">Paused</span>
                    )}
                  </p>
                  <p className="text-xs text-slate-500 truncate">
                    → {r.recipient_emails.join(', ')}
                  </p>
                  <p className="text-[11px] text-slate-400">
                    Next run: {new Date(r.next_run_at).toLocaleString()}
                    {r.last_run_at && ` · Last: ${new Date(r.last_run_at).toLocaleString()}`}
                  </p>
                </div>
                <button onClick={() => runNow(r.id)}
                        data-testid={`report-run-${r.id}`}
                        title="Run now"
                        className="p-2 rounded-lg text-emerald-600 hover:bg-emerald-50">
                  <Play className="h-4 w-4" />
                </button>
                <button onClick={() => toggle(r)}
                        data-testid={`report-toggle-${r.id}`}
                        title="Pause / resume"
                        className={`p-2 rounded-lg ${r.is_active ? 'text-indigo-600 hover:bg-indigo-50' : 'text-slate-400 hover:bg-slate-100'}`}>
                  <ToggleRight className="h-4 w-4" />
                </button>
                <button onClick={() => remove(r.id)}
                        data-testid={`report-delete-${r.id}`}
                        title="Delete"
                        className="p-2 rounded-lg text-rose-600 hover:bg-rose-50">
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

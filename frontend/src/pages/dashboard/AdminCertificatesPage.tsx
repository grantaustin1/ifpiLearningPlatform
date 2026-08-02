import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { toast } from 'sonner'
import { Search, XCircle, Download, ChevronLeft, ChevronRight, ShieldCheck, Clock, History, Mail, FileArchive, Undo2 } from 'lucide-react'
import { useConfirm } from 'components/ConfirmDialog'
import { usePrompt } from 'components/PromptDialog'

interface Row {
  id: number
  code: string
  type: string
  title: string | null
  recipient_name: string | null
  recipient_email: string | null
  issued_at: string
  revoked_at: string | null
  revoked_reason: string | null
  score: number | null
}
interface RevocationEvent {
  id: number
  action: 'REVOKE' | 'UNREVOKE'
  reason: string | null
  occurred_at: string
  actor_user_id: number
  actor_name: string | null
  actor_email: string | null
}

/**
 * Iter 30 — Bulk Certificate Operations (admin only).
 *
 * A searchable/filterable table of every certificate in the caller's
 * organisation with multi-select + bulk revoke + CSV export. Also
 * surfaces the per-certificate audit trail via a slide-out drawer
 * for compliance review.
 */
export default function AdminCertificatesPage() {
  const confirm = useConfirm()
  const prompt = usePrompt()
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'revoked'>('all')
  const [typeFilter, setTypeFilter] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [historyFor, setHistoryFor] = useState<Row | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['admin-certs', q, statusFilter, typeFilter, page],
    queryFn: async () => (await api.get('/certificates/admin-list', {
      params: {
        q: q || undefined,
        status: statusFilter,
        type: typeFilter || undefined,
        page, page_size: 25,
      },
    })).data as { total: number; page: number; page_size: number; items: Row[] },
  })

  const items = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.max(1, Math.ceil(total / 25))
  const allIds = items.map(r => r.id)
  const isAllSelected = allIds.length > 0 && allIds.every(id => selected.has(id))

  // Iter 31 — Split selection by revocation state so each bulk action
  // targets only the compatible subset (avoids server-side skipping).
  const selectedActiveIds = items.filter(r => selected.has(r.id) && !r.revoked_at).map(r => r.id)
  const selectedRevokedIds = items.filter(r => selected.has(r.id) && r.revoked_at).map(r => r.id)

  const toggle = (id: number) => setSelected(prev => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id); else next.add(id)
    return next
  })
  const toggleAll = () => setSelected(prev => {
    if (isAllSelected) return new Set()
    return new Set(allIds)
  })

  const bulkRevoke = async () => {
    if (selectedActiveIds.length === 0) return
    const reason = await prompt({
      title: 'Reason for revocation',
      description: `Optional — this note is written to the audit log for compliance review. ${selectedActiveIds.length} certificate${selectedActiveIds.length === 1 ? '' : 's'} will be revoked.`,
      placeholder: 'e.g. Issued in error / Learner request / Superseded by re-issue',
      multiline: true,
      maxLength: 255,
      confirmLabel: 'Continue',
    })
    if (reason === null) return  // user cancelled
    if (!(await confirm({
      title: `Revoke ${selectedActiveIds.length} certificate${selectedActiveIds.length === 1 ? '' : 's'}?`,
      description: 'Their public verify + share pages will show REVOKED. Learners can no longer download their PDF. This is reversible per-cert.',
      confirmLabel: `Revoke ${selectedActiveIds.length}`,
      variant: 'danger',
    }))) return
    try {
      const r = await api.post('/certificates/bulk-revoke', {
        certificate_ids: selectedActiveIds,
        reason: reason || null,
      })
      toast.success(`Revoked ${r.data.revoked_count} certificate${r.data.revoked_count === 1 ? '' : 's'} · ${r.data.skipped_count} skipped`)
      setSelected(new Set())
      qc.invalidateQueries({ queryKey: ['admin-certs'] })
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Bulk revoke failed')
    }
  }

  const bulkUnrevoke = async () => {
    if (selectedRevokedIds.length === 0) return
    if (!(await confirm({
      title: `Restore ${selectedRevokedIds.length} certificate${selectedRevokedIds.length === 1 ? '' : 's'}?`,
      description: 'The revoked flag will be cleared. Learners will regain PDF download access. An UNREVOKE event is written to the audit log for each cert.',
      confirmLabel: `Restore ${selectedRevokedIds.length}`,
    }))) return
    try {
      const r = await api.post('/certificates/bulk-unrevoke', {
        certificate_ids: selectedRevokedIds,
      })
      toast.success(`Restored ${r.data.unrevoked_count} · ${r.data.skipped_count} skipped`)
      setSelected(new Set())
      qc.invalidateQueries({ queryKey: ['admin-certs'] })
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Bulk unrevoke failed')
    }
  }

  const bulkEmail = async () => {
    if (selectedActiveIds.length === 0) return
    if (!(await confirm({
      title: `Email ${selectedActiveIds.length} learner${selectedActiveIds.length === 1 ? '' : 's'}?`,
      description: 'A certificate download + verification link will be queued to each learner via the standard email outbox.',
      confirmLabel: `Queue ${selectedActiveIds.length} email${selectedActiveIds.length === 1 ? '' : 's'}`,
    }))) return
    try {
      const r = await api.post('/certificates/bulk-email', {
        certificate_ids: selectedActiveIds,
      })
      toast.success(`Queued ${r.data.queued_count} email${r.data.queued_count === 1 ? '' : 's'}`)
      setSelected(new Set())
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Bulk email failed')
    }
  }

  const bulkDownloadZip = async () => {
    if (selectedActiveIds.length === 0) return
    if (selectedActiveIds.length > 100) {
      toast.error('Max 100 certificates per ZIP. Please narrow your selection.')
      return
    }
    try {
      const r = await api.post('/certificates/bulk-zip',
        { certificate_ids: selectedActiveIds },
        { responseType: 'blob' })
      const url = URL.createObjectURL(r.data)
      const a = document.createElement('a')
      a.href = url
      const count = r.headers['x-certs-bundled'] || selectedActiveIds.length
      a.download = `certificates-${count}.zip`
      a.click()
      URL.revokeObjectURL(url)
      toast.success(`Downloaded ${count} certificate${count === '1' ? '' : 's'} as ZIP`)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Bulk ZIP failed')
    }
  }

  const exportCsv = () => {
    // Use fetch so we can inject the cookie/CSRF creds
    api.get('/certificates/admin-export.csv', { responseType: 'blob' })
      .then(r => {
        const url = URL.createObjectURL(r.data)
        const a = document.createElement('a')
        a.href = url; a.download = 'certificates.csv'; a.click()
        URL.revokeObjectURL(url)
        toast.success('CSV downloaded')
      })
      .catch(() => toast.error('Export failed'))
  }

  return (
    <div className="p-8" data-testid="admin-certificates-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">Certificates</h1>
          <p className="text-slate-500 mt-1">{isLoading ? 'Loading…' : `${total} total in your organisation`}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={exportCsv} data-testid="export-csv-btn"
            className="inline-flex items-center gap-1.5 text-sm border border-slate-300 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-lg font-medium">
            <Download className="h-4 w-4" /> Export CSV
          </button>
          <button
            onClick={bulkEmail}
            disabled={selectedActiveIds.length === 0}
            data-testid="bulk-email-btn"
            className="inline-flex items-center gap-1.5 text-sm border border-slate-300 hover:bg-slate-50 disabled:border-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed text-slate-700 px-4 py-2 rounded-lg font-medium"
          >
            <Mail className="h-4 w-4" /> Email {selectedActiveIds.length > 0 ? `(${selectedActiveIds.length})` : ''}
          </button>
          <button
            onClick={bulkDownloadZip}
            disabled={selectedActiveIds.length === 0}
            data-testid="bulk-zip-btn"
            className="inline-flex items-center gap-1.5 text-sm border border-slate-300 hover:bg-slate-50 disabled:border-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed text-slate-700 px-4 py-2 rounded-lg font-medium"
          >
            <FileArchive className="h-4 w-4" /> Download ZIP {selectedActiveIds.length > 0 ? `(${selectedActiveIds.length})` : ''}
          </button>
          <button
            onClick={bulkUnrevoke}
            disabled={selectedRevokedIds.length === 0}
            data-testid="bulk-unrevoke-btn"
            className="inline-flex items-center gap-1.5 text-sm bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg font-semibold"
          >
            <Undo2 className="h-4 w-4" /> Restore {selectedRevokedIds.length > 0 ? `(${selectedRevokedIds.length})` : ''}
          </button>
          <button
            onClick={bulkRevoke}
            disabled={selectedActiveIds.length === 0}
            data-testid="bulk-revoke-btn"
            className="inline-flex items-center gap-1.5 text-sm bg-red-600 hover:bg-red-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg font-semibold"
          >
            <XCircle className="h-4 w-4" /> Revoke {selectedActiveIds.length > 0 ? `(${selectedActiveIds.length})` : ''}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input value={q} onChange={e => { setQ(e.target.value); setPage(1) }}
            placeholder="Search by learner name, email, or cert code…"
            data-testid="cert-search-input"
            className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm" />
        </div>
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value as any); setPage(1) }}
          data-testid="cert-status-filter"
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white">
          <option value="all">All statuses</option>
          <option value="active">Active only</option>
          <option value="revoked">Revoked only</option>
        </select>
        <select value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setPage(1) }}
          data-testid="cert-type-filter"
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white">
          <option value="">All types</option>
          <option value="COURSE_COMPLETION">Course completion</option>
          <option value="LIVE_SESSION_ATTENDANCE">Live session attendance</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200 text-xs uppercase text-slate-500">
            <tr>
              <th className="w-10 px-4 py-3">
                <input type="checkbox" checked={isAllSelected} onChange={toggleAll}
                  data-testid="select-all-checkbox" className="h-4 w-4 rounded" />
              </th>
              <th className="text-left px-3 py-3">Recipient</th>
              <th className="text-left px-3 py-3">Course / Session</th>
              <th className="text-left px-3 py-3">Type</th>
              <th className="text-left px-3 py-3">Issued</th>
              <th className="text-left px-3 py-3">Status</th>
              <th className="w-24 px-3 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {items.map(r => (
              <tr key={r.id} className={`border-b border-slate-100 ${r.revoked_at ? 'bg-red-50/30' : 'hover:bg-slate-50'}`}
                data-testid={`admin-cert-row-${r.id}`}>
                <td className="px-4 py-3">
                  <input type="checkbox"
                    checked={selected.has(r.id)}
                    onChange={() => toggle(r.id)}
                    data-testid={`select-cert-${r.id}`}
                    className="h-4 w-4 rounded" />
                </td>
                <td className="px-3 py-3">
                  <p className="font-medium text-slate-800">{r.recipient_name || r.recipient_email}</p>
                  <p className="text-xs text-slate-400">{r.recipient_email}</p>
                </td>
                <td className="px-3 py-3 max-w-xs truncate text-slate-700">{r.title || '—'}</td>
                <td className="px-3 py-3 text-xs text-slate-500">
                  {r.type === 'LIVE_SESSION_ATTENDANCE' ? 'Attendance' : 'Completion'}
                </td>
                <td className="px-3 py-3 text-xs text-slate-500">{new Date(r.issued_at).toLocaleDateString()}</td>
                <td className="px-3 py-3">
                  {r.revoked_at ? (
                    <span className="inline-flex items-center gap-1 text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                      <XCircle className="h-3 w-3" /> Revoked
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">
                      <ShieldCheck className="h-3 w-3" /> Active
                    </span>
                  )}
                </td>
                <td className="px-3 py-3 text-right">
                  <button onClick={() => setHistoryFor(r)} data-testid={`cert-history-${r.id}`}
                    className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-600">
                    <History className="h-3.5 w-3.5" /> History
                  </button>
                </td>
              </tr>
            ))}
            {!isLoading && items.length === 0 && (
              <tr><td colSpan={7} className="text-center py-12 text-slate-400" data-testid="admin-certs-empty">
                No certificates match your filters.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-4 text-sm text-slate-500">
        <span>Page {page} of {totalPages}</span>
        <div className="flex gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            data-testid="page-prev"
            className="px-3 py-1.5 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
            data-testid="page-next"
            className="px-3 py-1.5 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40">
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {historyFor && (
        <RevocationHistoryDrawer cert={historyFor} onClose={() => setHistoryFor(null)} />
      )}
    </div>
  )
}


function RevocationHistoryDrawer({ cert, onClose }: { cert: Row; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['cert-history', cert.id],
    queryFn: async () => (await api.get(`/certificates/${cert.id}/revocation-history`)).data as RevocationEvent[],
  })

  return (
    <div className="fixed inset-0 bg-black/40 flex justify-end z-50" onClick={onClose}
      data-testid="revocation-history-drawer">
      <div className="w-full max-w-md bg-white h-full overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="p-5 border-b border-slate-100">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Revocation history</h2>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600" data-testid="close-history">
              <XCircle className="h-4 w-4" />
            </button>
          </div>
          <p className="text-xs text-slate-500 mt-1 truncate">{cert.recipient_name} · {cert.title}</p>
          <p className="text-[11px] font-mono text-slate-400 mt-0.5">/{cert.code}</p>
        </div>
        <div className="p-5">
          {isLoading ? (
            <p className="text-sm text-slate-400 text-center py-8">Loading…</p>
          ) : !data || data.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-8" data-testid="history-empty">
              No revocation events yet — this certificate has never been revoked.
            </p>
          ) : (
            <ul className="space-y-3" data-testid="history-events">
              {data.map(e => (
                <li key={e.id} className="flex items-start gap-3" data-testid={`history-event-${e.id}`}>
                  <div className={`shrink-0 mt-0.5 rounded-full p-1.5
                    ${e.action === 'REVOKE' ? 'bg-red-100 text-red-600' : 'bg-emerald-100 text-emerald-600'}`}>
                    {e.action === 'REVOKE' ? <XCircle className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-800">{e.action === 'REVOKE' ? 'Revoked' : 'Unrevoked'}</p>
                    <p className="text-xs text-slate-500">
                      by {e.actor_name || e.actor_email || `User #${e.actor_user_id}`}
                    </p>
                    <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" />{new Date(e.occurred_at).toLocaleString()}
                    </p>
                    {e.reason && <p className="text-xs text-slate-600 mt-1 italic">&ldquo;{e.reason}&rdquo;</p>}
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

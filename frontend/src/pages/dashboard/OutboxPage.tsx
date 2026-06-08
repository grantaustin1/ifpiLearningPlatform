import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Mail, CheckCircle, AlertCircle, Clock, FileText, ChevronLeft, ChevronRight, Search, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { timeAgo } from 'lib/utils'

const PAGE_SIZE = 25

export default function OutboxPage() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [search, setSearch] = useState('')
  const qc = useQueryClient()

  const { data, isLoading } = useQuery<any>({
    queryKey: ['outbox', page, statusFilter, search],
    queryFn: async () => (await api.get('/admin/outbox', {
      params: { page, page_size: PAGE_SIZE, status: statusFilter || undefined, q: search || undefined },
    })).data,
  })
  const { data: stats = {} } = useQuery<any>({
    queryKey: ['outbox-stats'],
    queryFn: async () => (await api.get('/admin/outbox/stats')).data,
  })

  const messages = data?.messages || []
  const total = data?.total || 0
  const totalPages = data?.total_pages || 1

  return (
    <div className="p-8" data-testid="outbox-page">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 font-display">Email Outbox</h1>
        <p className="text-slate-500 mt-1 mb-6">{isLoading ? 'Loading…' : `${total} messages`}</p>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-6 flex items-start gap-3" data-testid="outbox-stub-banner">
        <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-amber-800">Async outbox worker · stub mode</p>
          <p className="text-xs text-amber-700 mt-0.5">
            Background worker drains queued emails every 5s. In stub mode they're marked STUB only — set <code className="bg-amber-100 px-1 rounded font-mono text-[11px]">BILLING_LIVE_MODE=true</code> + <code className="bg-amber-100 px-1 rounded font-mono text-[11px]">ERP360_BASE_URL</code> to dispatch via ERP360.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Stub (held)', value: stats.STUB || 0, icon: FileText, color: 'text-slate-500',  bg: 'bg-slate-50' },
          { label: 'Sent',        value: stats.SENT || 0, icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-50' },
          { label: 'Queued',      value: stats.QUEUED || 0, icon: Clock, color: 'text-amber-600',   bg: 'bg-amber-50' },
          { label: 'Failed',      value: stats.FAILED || 0, icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-50' },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-2xl shadow-sm p-5 flex items-center gap-4">
            <div className={`p-2.5 rounded-xl ${s.bg}`}><s.icon className={`h-5 w-5 ${s.color}`} /></div>
            <div><p className="text-2xl font-bold text-slate-900">{s.value}</p><p className="text-xs text-slate-500 mt-1">{s.label}</p></div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input value={search} onChange={e => { setSearch(e.target.value); setPage(1) }} placeholder="Search by email or subject…" data-testid="outbox-search"
            className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }} data-testid="outbox-status-filter"
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white">
          <option value="">All statuses</option>
          <option value="QUEUED">Queued</option>
          <option value="STUB">Stub</option>
          <option value="SENT">Sent</option>
          <option value="FAILED">Failed</option>
        </select>
      </div>

      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        {messages.length === 0 ? (
          <p className="py-10 text-center text-slate-400 text-sm">No emails match.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b"><tr>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Recipient</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Subject</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Template</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Attachments</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Status</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Created</th>
              <th className="text-right px-6 py-3 font-medium text-slate-500"></th>
            </tr></thead>
            <tbody className="divide-y">
              {messages.map((m: any) => (
                <tr key={m.id} data-testid={`outbox-row-${m.id}`}>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2"><Mail className="h-3.5 w-3.5 text-slate-400" /> <span className="font-medium">{m.to_email}</span></div>
                    {m.to_name && <p className="text-xs text-slate-400 ml-5 mt-0.5">{m.to_name}</p>}
                  </td>
                  <td className="px-6 py-4 truncate max-w-xs">{m.subject}</td>
                  <td className="px-6 py-4">{m.template && <span className="text-xs font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-600">{m.template}</span>}</td>
                  <td className="px-6 py-4 text-xs text-slate-500">{m.attachments?.length ? `${m.attachments.length} file${m.attachments.length > 1 ? 's' : ''}` : '—'}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full ${
                      m.status === 'SENT' ? 'bg-emerald-100 text-emerald-700' :
                      m.status === 'STUB' ? 'bg-slate-100 text-slate-600' :
                      m.status === 'QUEUED' ? 'bg-amber-100 text-amber-700' :
                      'bg-red-100 text-red-700'
                    }`}>{m.status}</span>
                  </td>
                  <td className="px-6 py-4 text-xs text-slate-500">{timeAgo(m.created_at)}</td>
                  <td className="px-6 py-4 text-right">
                    {(m.status === 'FAILED' || m.status === 'DEAD_LETTER') && (
                      <button
                        data-testid={`outbox-retry-${m.id}`}
                        onClick={async () => {
                          try {
                            await api.post(`/admin/outbox/${m.id}/retry`)
                            toast.success('Queued for retry')
                            qc.invalidateQueries({ queryKey: ['outbox'] })
                            qc.invalidateQueries({ queryKey: ['outbox-stats'] })
                          } catch (e: any) { toast.error(e?.response?.data?.detail || 'Retry failed') }
                        }}
                        className="inline-flex items-center gap-1 border border-slate-200 hover:bg-slate-50 text-xs rounded-md px-2 py-1 text-slate-600">
                        <RefreshCw className="h-3 w-3" /> Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 px-1" data-testid="outbox-pager">
          <span className="text-xs text-slate-500">Page {page} of {totalPages} · {total} total</span>
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} data-testid="outbox-prev"
              className="inline-flex items-center gap-1 border border-slate-200 hover:bg-slate-50 disabled:opacity-40 text-xs rounded-lg px-3 py-1.5">
              <ChevronLeft className="h-3.5 w-3.5" /> Prev
            </button>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages} data-testid="outbox-next"
              className="inline-flex items-center gap-1 border border-slate-200 hover:bg-slate-50 disabled:opacity-40 text-xs rounded-lg px-3 py-1.5">
              Next <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

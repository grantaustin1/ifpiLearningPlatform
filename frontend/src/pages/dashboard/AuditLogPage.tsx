import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Shield, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { timeAgo } from 'lib/utils'

const ACTION_COLORS: Record<string, string> = {
  THEME_APPLIED: 'bg-purple-50 text-purple-700',
  SMTP_CONFIG_UPDATED: 'bg-blue-50 text-blue-700',
  BADGE_TIER_CREATED: 'bg-emerald-50 text-emerald-700',
  BADGE_TIER_UPDATED: 'bg-amber-50 text-amber-700',
  BADGE_TIER_DELETED: 'bg-red-50 text-red-700',
  BADGE_TIERS_REORDERED: 'bg-indigo-50 text-indigo-700',
  ACADEMY_CREATED: 'bg-cyan-50 text-cyan-700',
  INVITATIONS_BULK_QUEUED: 'bg-pink-50 text-pink-700',
}

export default function AuditLogPage() {
  const [page, setPage] = useState(1)
  const [action, setAction] = useState('')
  const pageSize = 50

  const { data, isLoading } = useQuery<any>({
    queryKey: ['audit', page, action],
    queryFn: async () => (await api.get('/admin/audit-log', {
      params: { limit: pageSize, offset: (page - 1) * pageSize, action: action || undefined },
    })).data,
  })

  const items = data?.items || []
  const total = data?.total || 0

  return (
    <div className="space-y-6" data-testid="audit-log-page">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2"><Shield className="h-5 w-5 text-indigo-500" /> Audit log</h1>
        <p className="text-sm text-slate-500">Append-only record of who-did-what for compliance and forensic review.</p>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input value={action} onChange={e => { setAction(e.target.value); setPage(1) }}
            placeholder="Filter by action (e.g. THEME_APPLIED)…"
            data-testid="audit-action-filter"
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/40" />
        </div>
        <span className="text-xs text-slate-500 ml-auto">{total} entries</span>
      </div>

      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-sm text-slate-500">Loading…</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-sm text-slate-500">No audit entries match this filter.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-6 py-3 font-medium text-slate-500">When</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Actor</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Action</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Target</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((it: any) => (
                <tr key={it.id} className="hover:bg-slate-50" data-testid={`audit-row-${it.id}`}>
                  <td className="px-6 py-3 text-xs text-slate-500">{timeAgo(it.created_at)}</td>
                  <td className="px-6 py-3">
                    {it.actor ? <span className="text-slate-700">{it.actor.email}</span> : <span className="text-slate-400 italic">system</span>}
                  </td>
                  <td className="px-6 py-3">
                    <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${ACTION_COLORS[it.action] || 'bg-slate-100 text-slate-700'}`}>{it.action}</span>
                  </td>
                  <td className="px-6 py-3 text-xs text-slate-500">{it.target_type ? `${it.target_type}#${it.target_id}` : '—'}</td>
                  <td className="px-6 py-3 text-xs text-slate-600 font-mono max-w-md truncate" title={JSON.stringify(it.metadata)}>
                    {Object.keys(it.metadata || {}).length ? JSON.stringify(it.metadata) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {total > pageSize && (
          <div className="flex items-center justify-between px-6 py-3 border-t border-slate-200 bg-slate-50">
            <span className="text-xs text-slate-500">Page {page} of {Math.ceil(total / pageSize)}</span>
            <div className="flex gap-1">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="p-1.5 rounded-md border border-slate-200 hover:bg-white disabled:opacity-40"><ChevronLeft className="h-3.5 w-3.5" /></button>
              <button onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / pageSize)}
                className="p-1.5 rounded-md border border-slate-200 hover:bg-white disabled:opacity-40"><ChevronRight className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

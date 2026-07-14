import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Webhook, CheckCircle2, XCircle, Clock, AlertTriangle, Filter } from 'lucide-react'

interface Delivery {
  id: number
  subscription_id: number
  subscription_description: string | null
  target_url: string
  is_dry_run: boolean
  event_type: string
  event_id: string
  status: string
  status_code: number | null
  attempt_count: number
  error: string | null
  created_at: string
  delivered_at: string | null
}

const STATUS_ICON: Record<string, { icon: any; color: string }> = {
  DELIVERED:   { icon: CheckCircle2, color: 'text-emerald-600' },
  QUEUED:      { icon: Clock,        color: 'text-slate-400' },
  FAILED:      { icon: AlertTriangle, color: 'text-amber-500' },
  DEAD_LETTER: { icon: XCircle,      color: 'text-red-600' },
}

const EVENT_TYPES = [
  '',
  'learner.invited',
  'certificate.issued',
  'course.completed',
  'cohort.milestone_reached',
  'user.provisioned',
]

const STATUSES = ['', 'DELIVERED', 'QUEUED', 'FAILED', 'DEAD_LETTER']

const fmtTime = (iso: string | null) => {
  if (!iso) return '—'
  try {
    const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso }
}

export default function WebhookDeliveriesPage() {
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [eventFilter, setEventFilter] = useState<string>('')

  const { data, isLoading, refetch, isRefetching } = useQuery<{ items: Delivery[] }>({
    queryKey: ['webhook-deliveries', statusFilter, eventFilter],
    queryFn: async () => {
      const q = new URLSearchParams({ limit: '100' })
      if (statusFilter) q.set('status', statusFilter)
      if (eventFilter) q.set('event_type', eventFilter)
      return (await api.get(`/admin/webhooks/deliveries?${q}`)).data
    },
    refetchInterval: 15000,
  })

  const items = data?.items ?? []

  return (
    <div className="max-w-6xl space-y-6" data-testid="webhook-deliveries-page">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
            <Webhook className="h-6 w-6 text-indigo-600" />
            Webhook Deliveries
          </h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">
            Read-only view of recent outbound webhook events across all
            subscriptions in your org. Rows targeting <code className="text-xs bg-slate-100 px-1 rounded">dry-run://…</code>
            {' '}are queued + signed but never POSTed — flip the target
            URL on the subscription to go live.
          </p>
        </div>
        <button onClick={() => refetch()} disabled={isRefetching}
          data-testid="webhook-deliveries-refresh"
          className="text-sm text-slate-600 hover:text-slate-900 border border-slate-300 hover:border-slate-400 rounded-lg px-3 py-1.5">
          {isRefetching ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 flex flex-wrap gap-3 items-center">
        <Filter className="h-4 w-4 text-slate-400" />
        <label className="text-sm text-slate-700 flex items-center gap-2">
          Status:
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
            data-testid="webhook-status-filter"
            className="border border-slate-300 rounded-lg px-2 py-1 text-sm bg-white">
            {STATUSES.map(s => (
              <option key={s} value={s}>{s || 'All'}</option>
            ))}
          </select>
        </label>
        <label className="text-sm text-slate-700 flex items-center gap-2">
          Event:
          <select value={eventFilter} onChange={e => setEventFilter(e.target.value)}
            data-testid="webhook-event-filter"
            className="border border-slate-300 rounded-lg px-2 py-1 text-sm bg-white">
            {EVENT_TYPES.map(e => (
              <option key={e} value={e}>{e || 'All'}</option>
            ))}
          </select>
        </label>
        <span className="ml-auto text-xs text-slate-500">
          {items.length} row{items.length === 1 ? '' : 's'} · auto-refresh 15s
        </span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-slate-500">Loading…</div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">
            No deliveries match the current filters.
          </div>
        ) : (
          <table className="w-full text-sm" data-testid="webhook-deliveries-table">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Event</th>
                <th className="text-left px-4 py-3">Target</th>
                <th className="text-left px-4 py-3">Attempts</th>
                <th className="text-left px-4 py-3">Response</th>
                <th className="text-left px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map(row => {
                const meta = STATUS_ICON[row.status] ?? STATUS_ICON.QUEUED
                const Icon = meta.icon
                return (
                  <tr key={row.id} data-testid={`delivery-row-${row.id}`}
                    className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1.5">
                        <Icon className={`h-4 w-4 ${meta.color}`} />
                        <span className="text-xs font-medium text-slate-700">
                          {row.status}
                        </span>
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-slate-900 text-xs font-mono">
                        {row.event_type}
                      </div>
                      <div className="text-xs text-slate-400 font-mono">
                        {row.event_id.slice(0, 12)}…
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {row.is_dry_run ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs font-medium">
                          dry-run
                        </span>
                      ) : (
                        <span className="text-xs text-slate-700 font-mono truncate max-w-xs inline-block"
                          title={row.target_url}>
                          {row.target_url}
                        </span>
                      )}
                      {row.subscription_description && (
                        <div className="text-xs text-slate-400 mt-0.5">
                          {row.subscription_description}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {row.attempt_count}
                    </td>
                    <td className="px-4 py-3">
                      {row.status_code !== null && (
                        <div className="text-xs text-slate-700">
                          HTTP {row.status_code}
                        </div>
                      )}
                      {row.error && (
                        <div className="text-xs text-slate-500 truncate max-w-xs" title={row.error}>
                          {row.error}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
                      {fmtTime(row.created_at)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

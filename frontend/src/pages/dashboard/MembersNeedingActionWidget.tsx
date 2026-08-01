<<<<<<< HEAD
/** Iter 30k — "Members needing action" dashboard widget.
 *
 * Fetches /api/admin/dashboard/members-needing-action and renders a
 * prioritized action list. Colour-coded by reason:
 *   STALLED = rose (highest urgency)
 *   IDLE = amber
 *   NEVER_SIGNED_IN = slate
 */
import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Link } from 'react-router-dom'
import { AlertTriangle, UserX, Clock, ArrowRight, Users } from 'lucide-react'

type Item = {
  user_id: number
  email: string
  name: string
  reason_code: 'STALLED' | 'IDLE' | 'NEVER_SIGNED_IN'
  reason: string
  detail: string
  next_step: { label: string; path: string }
  priority: number
}

const REASON_META: Record<Item['reason_code'], { icon: any; bg: string; border: string; text: string; label: string }> = {
  STALLED:         { icon: AlertTriangle, bg: 'bg-rose-50',   border: 'border-rose-200',   text: 'text-rose-700',   label: 'Stalled' },
  IDLE:            { icon: Clock,         bg: 'bg-amber-50',  border: 'border-amber-200',  text: 'text-amber-700',  label: 'Idle' },
  NEVER_SIGNED_IN: { icon: UserX,         bg: 'bg-slate-100', border: 'border-slate-200',  text: 'text-slate-700',  label: 'No sign-in' },
}

export function MembersNeedingActionWidget() {
  const { data, isLoading } = useQuery({
    queryKey: ['members-needing-action'],
    queryFn: async () => (await api.get('/admin/dashboard/members-needing-action?limit=10')).data,
    staleTime: 60_000,
  })

  return (
    <div className="bg-white rounded-2xl card-glow overflow-hidden" data-testid="members-needing-action">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-indigo-600" />
          <h2 className="text-sm font-semibold text-slate-800">Members needing action</h2>
          {data?.total_flagged > 0 && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 border border-rose-200">
              {data.total_flagged}
            </span>
          )}
        </div>
        <Link to="/users" className="text-xs text-indigo-600 hover:text-indigo-700 font-semibold inline-flex items-center gap-1">
          View all users <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      {isLoading ? (
        <div className="py-10 text-center text-sm text-slate-400">Loading…</div>
      ) : !data?.items?.length ? (
        <div className="py-10 text-center text-sm text-emerald-600" data-testid="mna-empty">
          🎉 Everyone is on track!
        </div>
      ) : (
        <div className="divide-y divide-slate-50" data-testid="mna-list">
          {data.items.map((it: Item) => {
            const meta = REASON_META[it.reason_code] || REASON_META.IDLE
            const Icon = meta.icon
            return (
              <div key={`${it.reason_code}-${it.user_id}`}
                   className="flex items-start gap-3 px-6 py-3.5 hover:bg-slate-50 group"
                   data-testid={`mna-row-${it.user_id}`}>
                <div className={`mt-0.5 w-8 h-8 rounded-lg ${meta.bg} ${meta.border} border flex items-center justify-center flex-shrink-0`}>
                  <Icon className={`h-4 w-4 ${meta.text}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-semibold text-slate-900 truncate">{it.name}</p>
                    <span className={`inline-block text-[10px] px-2 py-0.5 rounded-full ${meta.bg} ${meta.text} font-semibold`}>
                      {meta.label}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 truncate">{it.reason}</p>
                  <p className="text-[11px] text-slate-400">{it.detail}</p>
                </div>
                <Link to={it.next_step.path}
                      className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 opacity-70 group-hover:opacity-100 whitespace-nowrap"
                      data-testid={`mna-action-${it.user_id}`}>
                  {it.next_step.label} →
                </Link>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
=======
import React from 'react';

export default function MembersNeedingActionWidget() {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6">
      <h2 className="text-sm font-semibold text-slate-800">Members Needing Action</h2>
      <p className="text-slate-500 mt-2 text-sm">No members pending action.</p>
    </div>
  );
>>>>>>> origin/main
}

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { BACKEND_URL } from 'lib/env'
import { MessageSquare, CheckCircle2, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'

const CAT_STYLE: Record<string, string> = {
  BUG: 'bg-red-50 text-red-600 border-red-100',
  IDEA: 'bg-amber-50 text-amber-700 border-amber-100',
  OTHER: 'bg-slate-50 text-slate-600 border-slate-200',
}

export default function FeedbackAdminPage() {
  const qc = useQueryClient()
  const { data: items = [], isLoading } = useQuery({
    queryKey: ['admin-feedback'],
    queryFn: async () => (await api.get('/admin/feedback')).data,
  })
  const statusMut = useMutation({
    mutationFn: async ({ id, status }: { id: number; status: string }) =>
      (await api.post(`/admin/feedback/${id}/status`, { status })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-feedback'] }),
    onError: () => toast.error('Could not update status'),
  })
  const newCount = items.filter((f: any) => f.status === 'NEW').length

  return (
    <div className="space-y-6" data-testid="feedback-admin-page">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <MessageSquare className="h-6 w-6 text-indigo-500" /> Feedback
        </h1>
        <p className="text-sm text-slate-500 mt-1">{newCount} new · {items.length} total — submitted via the in-app widget</p>
      </div>
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        {isLoading ? (
          <p className="text-sm text-slate-400 p-8 text-center">Loading…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-slate-400 p-8 text-center">No feedback yet. The floating button (bottom-right) is available to every user.</p>
        ) : (
          <div className="divide-y divide-slate-50">
            {items.map((f: any) => (
              <div key={f.id} className={`px-5 py-4 flex gap-4 ${f.status === 'REVIEWED' ? 'opacity-60' : ''}`} data-testid={`feedback-row-${f.id}`}>
                <span className={`self-start text-[10px] font-semibold px-2 py-0.5 rounded-full border ${CAT_STYLE[f.category] || CAT_STYLE.OTHER}`}>{f.category}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-800 whitespace-pre-wrap">{f.message}</p>
                  {f.screenshot_url && (
                    <a href={f.screenshot_url.startsWith('http') ? f.screenshot_url : `${BACKEND_URL}${f.screenshot_url}`}
                      target="_blank" rel="noopener noreferrer"
                      data-testid={`feedback-screenshot-${f.id}`}
                      className="inline-block mt-2 rounded-lg border border-slate-200 overflow-hidden hover:border-indigo-300 transition-colors">
                      <img
                        src={f.screenshot_url.startsWith('http') ? f.screenshot_url : `${BACKEND_URL}${f.screenshot_url}`}
                        alt="Attached screenshot" className="h-24 object-cover" loading="lazy" />
                    </a>
                  )}
                  <p className="text-[11px] text-slate-400 mt-1.5">
                    {f.user_name} ({f.user_email}) · {f.page || '—'} · {f.created_at ? new Date(f.created_at + 'Z').toLocaleString() : ''}
                  </p>
                </div>
                <button
                  onClick={() => statusMut.mutate({ id: f.id, status: f.status === 'NEW' ? 'REVIEWED' : 'NEW' })}
                  data-testid={`feedback-status-${f.id}`}
                  className={`self-start inline-flex items-center gap-1 text-xs font-medium rounded-lg px-2.5 py-1.5 ${f.status === 'NEW' ? 'text-emerald-600 hover:bg-emerald-50' : 'text-slate-400 hover:bg-slate-50'}`}>
                  {f.status === 'NEW' ? <><CheckCircle2 className="h-3.5 w-3.5" /> Mark reviewed</> : <><RotateCcw className="h-3.5 w-3.5" /> Reopen</>}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

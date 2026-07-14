import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Search, CheckCircle2, XCircle, Info } from 'lucide-react'
import { toast } from 'sonner'

interface CourseEntitlement {
  course_id: number
  course_title: string
  price_cents: number
  currency: string
  entitled: boolean
  reason: string
  reason_human: string
}

interface UserEntitlementsResponse {
  user_id: number
  email: string
  organization_id: number
  entitlements: CourseEntitlement[]
}

const REASON_CHIP: Record<string, { label: string; className: string }> = {
  free:        { label: 'Free',         className: 'bg-slate-100 text-slate-700' },
  comp_role:   { label: 'Comp / staff', className: 'bg-purple-100 text-purple-800' },
  subscription:{ label: 'Subscription', className: 'bg-emerald-100 text-emerald-800' },
  none:        { label: 'No access',    className: 'bg-red-100 text-red-800' },
}

export default function EntitlementsInspectorPage() {
  const [userIdInput, setUserIdInput] = useState<string>('')
  const [includeFree, setIncludeFree] = useState<boolean>(false)
  const [result, setResult] = useState<UserEntitlementsResponse | null>(null)

  const lookupMut = useMutation({
    mutationFn: async ({ uid, includeFree }: { uid: number; includeFree: boolean }) => {
      const q = includeFree ? '?include_free=true' : ''
      return (await api.get(`/admin/entitlements/user/${uid}${q}`)).data as UserEntitlementsResponse
    },
    onSuccess: (data) => { setResult(data) },
    onError: (e: any) => {
      const msg = e?.response?.data?.error?.message
        || e?.response?.data?.detail
        || 'Lookup failed'
      toast.error(msg)
      setResult(null)
    },
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const uid = parseInt(userIdInput.trim(), 10)
    if (!uid || Number.isNaN(uid)) {
      toast.error('Enter a valid numeric user id')
      return
    }
    lookupMut.mutate({ uid, includeFree })
  }

  return (
    <div className="max-w-4xl space-y-6" data-testid="entitlements-inspector-page">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
          <Search className="h-6 w-6 text-indigo-600" />
          Entitlements Inspector
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Look up any user in your organization and see which courses
          they can access, plus the reason (subscription, comp role,
          free) or the remediation path when they can't.
        </p>
      </div>

      <form onSubmit={submit}
        className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <input type="number" min="1"
            value={userIdInput}
            onChange={e => setUserIdInput(e.target.value)}
            placeholder="User ID (e.g. 42)"
            data-testid="entitlements-user-id-input"
            className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500" />
          <button type="submit" disabled={lookupMut.isPending}
            data-testid="entitlements-lookup-btn"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg">
            {lookupMut.isPending ? 'Looking up…' : 'Look up'}
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer"
          data-testid="entitlements-include-free-toggle">
          <input type="checkbox" checked={includeFree}
            onChange={e => setIncludeFree(e.target.checked)}
            className="h-4 w-4 accent-indigo-600" />
          Include free courses (default: paid only)
        </label>
      </form>

      {result && (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden"
          data-testid="entitlements-result">
          <div className="bg-slate-50 border-b border-slate-200 px-5 py-3">
            <div className="text-sm font-medium text-slate-900">
              {result.email}
            </div>
            <div className="text-xs text-slate-500">
              User #{result.user_id} · Organization #{result.organization_id} ·
              {' '}{result.entitlements.length} course{result.entitlements.length === 1 ? '' : 's'}
            </div>
          </div>

          {result.entitlements.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-500">
              No matching courses. Try enabling "Include free courses".
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {result.entitlements.map(row => (
                <li key={row.course_id} className="p-5 flex items-start gap-4"
                  data-testid={`entitlements-row-${row.course_id}`}>
                  <div className="mt-1">
                    {row.entitled
                      ? <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                      : <XCircle className="h-5 w-5 text-red-500" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-slate-900 truncate">
                          {row.course_title}
                        </div>
                        <div className="text-xs text-slate-500">
                          Course #{row.course_id} · {row.price_cents === 0
                            ? 'Free'
                            : `${row.currency} ${(row.price_cents / 100).toFixed(2)}`}
                        </div>
                      </div>
                      <span className={
                        'inline-flex items-center whitespace-nowrap px-2 py-0.5 rounded text-xs font-medium '
                        + (REASON_CHIP[row.reason]?.className ?? 'bg-slate-100 text-slate-700')
                      }>
                        {REASON_CHIP[row.reason]?.label ?? row.reason}
                      </span>
                    </div>
                    {row.reason_human && (
                      <div className="mt-2 flex items-start gap-2 text-xs text-slate-600">
                        <Info className="h-3 w-3 mt-0.5 shrink-0 text-slate-400" />
                        <span>{row.reason_human}</span>
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

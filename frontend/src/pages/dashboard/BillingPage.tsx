import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { CreditCard, AlertCircle } from 'lucide-react'
import { formatCurrency } from 'lib/utils'

export default function BillingPage() {
  const { data: subs = [], isLoading } = useQuery<any[]>({
    queryKey: ['my-subs'], queryFn: async () => (await api.get('/billing/subscriptions')).data,
  })

  return (
    <div className="p-8 space-y-6" data-testid="billing-page">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 font-display">Subscriptions</h1>
        <p className="text-slate-500 mt-1">Your active and historical subscriptions</p>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-start gap-3" data-testid="billing-stub-banner">
        <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-amber-800">Billing is in stub mode</p>
          <p className="text-xs text-amber-700 mt-0.5">
            Subscriptions auto-activate without real payment. To enable live billing through ERP360, set <code className="bg-amber-100 px-1 rounded font-mono text-[11px]">BILLING_LIVE_MODE=true</code> and provide <code className="bg-amber-100 px-1 rounded font-mono text-[11px]">ERP360_BASE_URL</code> + secrets.
          </p>
        </div>
      </div>

      {isLoading ? <div className="flex items-center justify-center py-16"><div className="w-7 h-7 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div> :
       subs.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <CreditCard className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          No subscriptions yet. Subscribe to a paid course from the catalog.
        </div>
      ) : (
        <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b"><tr>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Product</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Status</th>
              <th className="text-right px-6 py-3 font-medium text-slate-500">Amount</th>
              <th className="text-right px-6 py-3 font-medium text-slate-500">Next billing</th>
            </tr></thead>
            <tbody className="divide-y">
              {subs.map((s: any) => (
                <tr key={s.id} data-testid={`sub-row-${s.id}`}>
                  <td className="px-6 py-4 font-medium">{s.product_code}</td>
                  <td className="px-6 py-4"><span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                    s.status === 'ACTIVE' ? 'bg-emerald-100 text-emerald-700' :
                    s.status === 'PAST_DUE' ? 'bg-amber-100 text-amber-700' :
                    s.status === 'CANCELLED' ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-600'
                  }`}>{s.status}</span></td>
                  <td className="px-6 py-4 text-right">{formatCurrency(s.amount_cents, s.currency)}</td>
                  <td className="px-6 py-4 text-right text-slate-500">{s.next_billing_date || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Mail, CheckCircle, AlertCircle, Clock, FileText, Send } from 'lucide-react'
import { timeAgo } from 'lib/utils'

export default function OutboxPage() {
  const { data: messages = [], isLoading } = useQuery<any[]>({
    queryKey: ['outbox'], queryFn: async () => (await api.get('/admin/outbox')).data,
  })

  const counts = messages.reduce((a: any, m: any) => {
    a[m.status] = (a[m.status] || 0) + 1; return a
  }, {})

  return (
    <div className="p-8" data-testid="outbox-page">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 font-display">Email Outbox</h1>
        <p className="text-slate-500 mt-1 mb-6">{isLoading ? 'Loading…' : `${messages.length} messages`}</p>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-6 flex items-start gap-3" data-testid="outbox-stub-banner">
        <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-amber-800">Email is in stub mode</p>
          <p className="text-xs text-amber-700 mt-0.5">
            Messages are persisted here but NOT actually delivered. Set <code className="bg-amber-100 px-1 rounded font-mono text-[11px]">BILLING_LIVE_MODE=true</code> + <code className="bg-amber-100 px-1 rounded font-mono text-[11px]">ERP360_BASE_URL</code> to route real emails through ERP360's mail transport.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Stub (held)', value: counts.STUB || 0, icon: FileText, color: 'text-slate-500',  bg: 'bg-slate-50' },
          { label: 'Sent',        value: counts.SENT || 0, icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-50' },
          { label: 'Queued',      value: counts.QUEUED || 0, icon: Clock, color: 'text-amber-600',   bg: 'bg-amber-50' },
          { label: 'Failed',      value: counts.FAILED || 0, icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-50' },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-2xl shadow-sm p-5 flex items-center gap-4">
            <div className={`p-2.5 rounded-xl ${s.bg}`}><s.icon className={`h-5 w-5 ${s.color}`} /></div>
            <div><p className="text-2xl font-bold text-slate-900">{s.value}</p><p className="text-xs text-slate-500 mt-1">{s.label}</p></div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        {messages.length === 0 ? (
          <p className="py-10 text-center text-slate-400 text-sm">No emails yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b"><tr>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Recipient</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Subject</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Template</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Attachments</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Status</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Created</th>
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
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

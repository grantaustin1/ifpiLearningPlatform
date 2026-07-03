/**
 * Iter 30r — Email transport diagnostics.
 *
 * Admin page to inspect which delivery transport is active + fire a
 * test email through the real pipeline. Useful when setting up per-org
 * SMTP or validating a new system-level relay.
 */
import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { Mail, CheckCircle2, XCircle, Send, ChevronRight, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

type Transport = { transport: string; configured: boolean; note: string }
type Status = { active_transport: string; transports: Transport[] }
type TestResult = { outbox_id: number; status: string; note: string; transport_message_id: string | null }

const TRANSPORT_LABEL: Record<string, string> = {
  per_tenant: 'Per-tenant SMTP',
  system: 'System SMTP relay (SES / SendGrid / etc.)',
  erp360: 'ERP360 notification bridge',
  stub: 'Stub — logged, not delivered',
}

export default function EmailDiagnosticsPage() {
  const [status, setStatus] = useState<Status | null>(null)
  const [toEmail, setToEmail] = useState('')
  const [subject, setSubject] = useState('[IFPI] SMTP test')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<TestResult | null>(null)
  const [error, setError] = useState('')

  const load = () => api.get('/admin/email/transport-status').then(r => setStatus(r.data))
  useEffect(() => { load() }, [])

  const send = async () => {
    setBusy(true); setError(''); setResult(null)
    try {
      const r = await api.post('/admin/email/send-test', { to_email: toEmail, subject })
      setResult(r.data)
      toast.success(r.data.status === 'SENT' ? 'Sent — check inbox' : `Status: ${r.data.status}`)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Test send failed')
      toast.error(e?.response?.data?.detail || 'Test send failed')
    } finally { setBusy(false) }
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6" data-testid="email-diagnostics-page">
      <header className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center">
          <Mail className="h-5 w-5 text-indigo-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Email diagnostics</h1>
          <p className="text-sm text-slate-500">
            Verify your outbound email pipeline is delivering.
          </p>
        </div>
      </header>

      {status && (
        <section className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-800">Active transport</h2>
            <span className="text-xs font-bold px-2 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100 uppercase">
              {status.active_transport}
            </span>
          </div>
          <ul className="divide-y divide-slate-100">
            {status.transports.map(t => (
              <li key={t.transport} className="flex items-start gap-3 px-5 py-3" data-testid={`transport-${t.transport}`}>
                {t.configured
                  ? <CheckCircle2 className="h-5 w-5 text-emerald-500 mt-0.5 flex-shrink-0" />
                  : <XCircle className="h-5 w-5 text-slate-300 mt-0.5 flex-shrink-0" />}
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-800">
                    {TRANSPORT_LABEL[t.transport] || t.transport}
                    {status.active_transport === t.transport && (
                      <span className="ml-2 text-[10px] font-bold text-emerald-700 uppercase">Active</span>
                    )}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">{t.note}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="bg-white border border-slate-200 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-slate-800 mb-3">Send test email</h2>
        <div className="grid gap-3 sm:grid-cols-[1fr_2fr] mb-3">
          <input value={subject} onChange={e => setSubject(e.target.value)}
                 placeholder="Subject" data-testid="email-test-subject"
                 className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          <input value={toEmail} onChange={e => setToEmail(e.target.value)}
                 placeholder="Recipient email" type="email" data-testid="email-test-to"
                 className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
        </div>
        <button onClick={send} disabled={busy || !toEmail.includes('@')}
                data-testid="email-test-send-btn"
                className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-sm font-semibold px-4 py-2 rounded-lg">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          Send test
        </button>

        {error && (
          <div className="mt-3 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3" data-testid="email-test-error">
            {error}
          </div>
        )}
        {result && (
          <div className="mt-3 text-sm bg-emerald-50 border border-emerald-200 rounded-lg p-3" data-testid="email-test-result">
            <p className="font-semibold text-emerald-800">Outbox #{result.outbox_id} → {result.status}</p>
            <p className="text-emerald-700 text-xs mt-1">{result.note}</p>
          </div>
        )}
      </section>

      <section className="bg-slate-50 border border-slate-200 rounded-xl p-5 text-sm text-slate-600">
        <h3 className="font-semibold text-slate-800 mb-2 flex items-center gap-1">
          <ChevronRight className="h-4 w-4" /> Configuring a system SMTP relay
        </h3>
        <p className="mb-2">
          Set these env vars on the backend to enable a global SMTP fallback
          (used when the current org has no per-tenant SMTP):
        </p>
        <pre className="bg-slate-900 text-slate-100 rounded p-3 text-xs font-mono overflow-x-auto">
{`SYSTEM_SMTP_HOST=email-smtp.eu-west-1.amazonaws.com
SYSTEM_SMTP_PORT=587
SYSTEM_SMTP_USERNAME=<your-ses-smtp-username>
SYSTEM_SMTP_PASSWORD=<your-ses-smtp-password>
SYSTEM_SMTP_USE_TLS=true
SYSTEM_SMTP_FROM_EMAIL=noreply@yourdomain.com
SYSTEM_SMTP_FROM_NAME=IFPI Learning`}
        </pre>
        <p className="mt-2 text-xs text-slate-500">
          Works with any SMTP provider: AWS SES, SendGrid (SMTP relay), Mailgun,
          Postmark, Fastmail, or self-hosted Postfix. TLS on port 587 recommended.
        </p>
      </section>
    </div>
  )
}

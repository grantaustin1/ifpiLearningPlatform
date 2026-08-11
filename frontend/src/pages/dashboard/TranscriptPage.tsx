import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from 'lib/api'
import { ArrowLeft, Award, Printer, ShieldCheck, XCircle } from 'lucide-react'

export default function TranscriptPage() {
  const nav = useNavigate()
  const { data, isLoading } = useQuery<any>({
    queryKey: ['transcript'],
    queryFn: async () => (await api.get('/certificates/transcript.json')).data,
  })

  if (isLoading || !data) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  const accent = data.organization?.primary_color || '#6366f1'
  const fmtDate = (iso?: string | null) =>
    iso ? new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '—'

  return (
    <div className="min-h-screen bg-slate-100 print:bg-white" data-testid="transcript-page">
      <div className="max-w-3xl mx-auto p-6 print:p-0">
        <div className="flex items-center justify-between mb-4 print:hidden">
          <button onClick={() => nav('/certificates')} data-testid="transcript-back-btn"
            className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900">
            <ArrowLeft className="h-4 w-4" /> Back to certificates
          </button>
          <button onClick={() => window.print()} data-testid="transcript-print-btn"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">
            <Printer className="h-4 w-4" /> Print
          </button>
        </div>

        <div className="bg-white rounded-2xl shadow-sm overflow-hidden print:shadow-none print:rounded-none">
          <div className="px-8 py-6 text-white" style={{ background: accent }}>
            <h1 className="text-2xl font-bold font-display">Learner Transcript</h1>
            <p className="text-sm opacity-90 mt-1">{data.organization?.name}</p>
          </div>

          <div className="px-8 py-6 border-b">
            <p className="text-lg font-semibold text-slate-900" data-testid="transcript-learner-name">
              {data.learner?.name || data.learner?.email}
            </p>
            <div className="text-sm text-slate-500 mt-1 space-y-0.5">
              <p>{data.learner?.email}</p>
              {data.learner?.cohort && <p>Cohort: {data.learner.cohort}</p>}
              <p>Total XP: {data.learner?.total_xp ?? 0} · Generated {fmtDate(data.generated_at)}</p>
            </div>
          </div>

          <div className="px-8 py-6 border-b">
            <h2 className="text-sm font-bold uppercase tracking-wide mb-3" style={{ color: accent }}>
              Completed courses ({data.courses?.length || 0})
            </h2>
            {(!data.courses || data.courses.length === 0) ? (
              <p className="text-sm text-slate-400">No courses completed yet.</p>
            ) : (
              <table className="w-full text-sm" data-testid="transcript-courses-table">
                <thead>
                  <tr className="text-left text-xs text-slate-400 border-b">
                    <th className="py-2 font-medium">Course</th>
                    <th className="py-2 font-medium">Completed</th>
                    <th className="py-2 font-medium text-right">Best score</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data.courses.map((c: any) => (
                    <tr key={c.id}>
                      <td className="py-2.5 font-medium text-slate-800">{c.title}</td>
                      <td className="py-2.5 text-slate-500">{fmtDate(c.completed_at)}</td>
                      <td className="py-2.5 text-right text-slate-700">
                        {c.best_score != null ? `${Math.round(c.best_score)}%` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="px-8 py-6 border-b">
            <h2 className="text-sm font-bold uppercase tracking-wide mb-3" style={{ color: accent }}>
              Certificates ({data.certificates?.length || 0})
            </h2>
            {(!data.certificates || data.certificates.length === 0) ? (
              <p className="text-sm text-slate-400">No certificates yet.</p>
            ) : (
              <table className="w-full text-sm" data-testid="transcript-certs-table">
                <thead>
                  <tr className="text-left text-xs text-slate-400 border-b">
                    <th className="py-2 font-medium">Certificate</th>
                    <th className="py-2 font-medium">Issued</th>
                    <th className="py-2 font-medium">Verify code</th>
                    <th className="py-2 font-medium text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data.certificates.map((c: any) => (
                    <tr key={c.id}>
                      <td className="py-2.5 font-medium text-slate-800">
                        {c.title}
                        {c.type === 'LIVE_SESSION_ATTENDANCE' && <span className="ml-2 text-[10px] text-slate-400 uppercase">attendance</span>}
                      </td>
                      <td className="py-2.5 text-slate-500">{fmtDate(c.issued_at)}</td>
                      <td className="py-2.5 font-mono text-xs text-slate-500">{c.code}</td>
                      <td className="py-2.5 text-right">
                        {c.revoked
                          ? <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600"><XCircle className="h-3.5 w-3.5" /> Revoked</span>
                          : <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600"><ShieldCheck className="h-3.5 w-3.5" /> Valid</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {data.badges?.length > 0 && (
            <div className="px-8 py-6 border-b">
              <h2 className="text-sm font-bold uppercase tracking-wide mb-3" style={{ color: accent }}>
                Badges ({data.badges.length})
              </h2>
              <div className="flex flex-wrap gap-2">
                {data.badges.map((b: any, i: number) => (
                  <span key={i} className="inline-flex items-center gap-1.5 text-xs font-medium bg-amber-50 border border-amber-200 text-amber-700 px-2.5 py-1 rounded-full">
                    <Award className="h-3 w-3" /> {b.badge}
                  </span>
                ))}
              </div>
            </div>
          )}

          <p className="px-8 py-4 text-[11px] text-slate-400 italic">
            Issued by {data.organization?.name}. This document does not constitute a certificate of credit
            unless accompanied by individual course certificates. Verify any certificate at /verify/&lt;code&gt;.
          </p>
        </div>
      </div>
    </div>
  )
}

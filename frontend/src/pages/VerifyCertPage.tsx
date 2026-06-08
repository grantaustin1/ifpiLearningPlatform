import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from 'lib/api'
import { CheckCircle2, XCircle, Award } from 'lucide-react'

export default function VerifyCertPage() {
  const { code } = useParams()
  const [cert, setCert] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get(`/certificates/verify/${code}`)
      .then(r => setCert(r.data))
      .catch(e => setError(e?.response?.data?.detail || 'Certificate not found'))
  }, [code])

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4" data-testid="verify-page">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center">
        {error ? (
          <>
            <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4"><XCircle className="h-8 w-8 text-red-600" /></div>
            <h1 className="text-xl font-bold text-slate-900">Certificate not valid</h1>
            <p className="text-slate-500 text-sm mt-1">{error}</p>
          </>
        ) : !cert ? <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" /> : (
          <>
            <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4"><CheckCircle2 className="h-8 w-8 text-emerald-600" /></div>
            <h1 className="text-xl font-bold text-slate-900">Certificate is valid</h1>
            <div className="mt-6 bg-slate-50 rounded-xl p-5 text-left space-y-3">
              <Row label="Recipient" value={cert.recipient_name} />
              <Row label="Course" value={cert.course_title} />
              <Row label="Type" value={cert.type} />
              <Row label="Verification code" value={cert.code} mono />
              <Row label="Issued" value={new Date(cert.issued_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })} />
            </div>
            <div className="mt-6 inline-flex items-center gap-2 text-amber-600"><Award className="h-5 w-5" /> IFPI Learning Platform</div>
          </>
        )}
      </div>
    </div>
  )
}

function Row({ label, value, mono = false }: any) {
  if (!value) return null
  return <div className="flex items-start justify-between gap-3"><span className="text-xs text-slate-500">{label}</span><span className={`text-sm font-medium text-slate-800 text-right ${mono ? 'font-mono text-xs' : ''}`}>{value}</span></div>
}

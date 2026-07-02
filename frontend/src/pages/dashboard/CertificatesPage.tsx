import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Award, Download, FileText, Linkedin, Link2, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'

export default function CertificatesPage() {
  const { data: certs = [], isLoading } = useQuery<any[]>({
    queryKey: ['certificates'], queryFn: async () => (await api.get('/certificates')).data,
  })

  const downloadTranscript = async () => {
    try {
      const r = await api.get('/certificates/transcript', { responseType: 'blob' })
      const url = URL.createObjectURL(r.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'IFPI-Transcript.pdf'
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
      toast.success('Transcript downloaded')
    } catch (e: any) {
      toast.error('Could not download transcript')
    }
  }

  const downloadPdf = async (cert: any) => {
    try {
      const r = await api.get(`/certificates/${cert.id}/pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(r.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `IFPI-Certificate-${cert.code}.pdf`
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      toast.error('Could not download certificate')
    }
  }

  const verifyUrl = (code: string) => `${window.location.origin}/verify/${encodeURIComponent(code)}`

  const copyLink = (cert: any) => {
    const url = verifyUrl(cert.code)
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(() => toast.success('Verify link copied'))
    } else {
      window.prompt('Copy this link:', url)
    }
  }

  const shareLinkedIn = (cert: any) => {
    // LinkedIn "Add to profile" flow — pre-fills their certifications section.
    // Docs: https://addtoprofile.linkedin.com/
    const url = verifyUrl(cert.code)
    const issued = cert.issued_at ? new Date(cert.issued_at) : new Date()
    const params = new URLSearchParams({
      startTask: 'CERTIFICATION_NAME',
      name: cert.course_title || 'IFPI Certificate',
      organizationName: 'IFPI Learning',
      issueYear: String(issued.getFullYear()),
      issueMonth: String(issued.getMonth() + 1),
      certUrl: url,
      certId: cert.code,
    })
    window.open(
      `https://www.linkedin.com/profile/add?${params.toString()}`,
      '_blank', 'noopener,noreferrer,width=780,height=680',
    )
  }

  return (
    <div className="p-8" data-testid="certificates-page">
      <div className="flex items-start justify-between mb-8 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">Certificates</h1>
          <p className="text-slate-500 mt-1">{isLoading ? 'Loading…' : `${certs.length} certificates`}</p>
        </div>
        <button onClick={downloadTranscript} data-testid="download-transcript-btn"
          className="inline-flex items-center gap-2 border border-slate-200 hover:bg-slate-50 text-slate-700 text-sm font-semibold px-4 py-2 rounded-lg">
          <FileText className="h-4 w-4" /> Download transcript
        </button>
      </div>
      {certs.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <Award className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          No certificates yet — complete a course to earn one.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="cert-grid">
          {certs.map(c => (
            <div key={c.id} className="bg-white rounded-2xl shadow-sm p-5 border border-slate-200 hover:border-amber-300 hover:shadow-lg transition" data-testid={`cert-${c.id}`}>
              <div className="flex items-start gap-3">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-100 to-amber-200 flex items-center justify-center flex-shrink-0"><Award className="h-6 w-6 text-amber-600" /></div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-900 truncate">{c.course_title || 'Certificate'}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{c.type}</p>
                  <p className="text-[11px] text-slate-400 mt-1 font-mono truncate">/{c.code}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-4">
                <button onClick={() => downloadPdf(c)} data-testid={`cert-download-${c.id}`}
                  className="inline-flex items-center justify-center gap-1.5 text-xs bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-2 rounded-lg font-semibold">
                  <Download className="h-3.5 w-3.5" /> Download PDF
                </button>
                <button onClick={() => copyLink(c)} data-testid={`cert-copy-${c.id}`}
                  className="inline-flex items-center justify-center gap-1.5 text-xs border border-slate-300 hover:bg-slate-50 text-slate-700 px-3 py-2 rounded-lg font-semibold">
                  <Link2 className="h-3.5 w-3.5" /> Copy link
                </button>
                <button onClick={() => shareLinkedIn(c)} data-testid={`cert-linkedin-${c.id}`}
                  className="inline-flex items-center justify-center gap-1.5 text-xs bg-[#0A66C2] hover:bg-[#004182] text-white px-3 py-2 rounded-lg font-semibold">
                  <Linkedin className="h-3.5 w-3.5" /> Add to LinkedIn
                </button>
                <a href={verifyUrl(c.code)} target="_blank" rel="noreferrer"
                  data-testid={`cert-verify-${c.id}`}
                  className="inline-flex items-center justify-center gap-1.5 text-xs border border-emerald-300 text-emerald-700 hover:bg-emerald-50 px-3 py-2 rounded-lg font-semibold">
                  <ShieldCheck className="h-3.5 w-3.5" /> Verify
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

<<<<<<< HEAD
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Award, Download, FileText, Linkedin, Link2, ShieldCheck, Share2, XCircle, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from 'contexts/AuthContext'
import { useConfirm } from 'components/ConfirmDialog'
import { usePrompt } from 'components/PromptDialog'

export default function CertificatesPage() {
  const { hasRole } = useAuth()
  const isAdmin = hasRole('ADMIN', 'SUPER_ADMIN')
  const confirm = useConfirm()
  const prompt = usePrompt()
  const qc = useQueryClient()
=======
import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Award, Download, ExternalLink, FileText, Link2, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'

export default function CertificatesPage() {
>>>>>>> origin/main
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
<<<<<<< HEAD
  const shareUrl = (code: string) => `${window.location.origin}/api/seo/certificates/share/${encodeURIComponent(code)}`

  const copyShareLink = (cert: any) => {
    const url = shareUrl(cert.code)
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(() =>
        toast.success('Share link copied · paste on LinkedIn or Twitter for a rich preview')
      )
    } else {
      prompt({
        title: 'Copy this share link',
        description: 'Your browser blocked automatic copy. Select the text and copy it manually.',
        defaultValue: url,
        confirmLabel: 'Done',
        cancelLabel: 'Close',
      })
    }
  }

  // Iter 29 — Admin revoke / unrevoke actions. Revoked certs get a
  // red REVOKED ribbon on the public share/verify pages + a 410 Gone
  // on the PDF download for non-admins.
  const revokeCert = async (cert: any) => {
    if (!(await confirm({
      title: 'Revoke this certificate?',
      description: `The public share page and OG preview will show "REVOKED". The learner can no longer download the PDF. This action is reversible.`,
      confirmLabel: 'Revoke',
      variant: 'danger',
    }))) return
    try {
      await api.post(`/certificates/${cert.id}/revoke`, { reason: 'Revoked by admin' })
      toast.success('Certificate revoked · social previews will refresh within minutes')
      qc.invalidateQueries({ queryKey: ['certificates'] })
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Revoke failed')
    }
  }
  const unrevokeCert = async (cert: any) => {
    try {
      await api.post(`/certificates/${cert.id}/unrevoke`)
      toast.success('Revocation lifted')
      qc.invalidateQueries({ queryKey: ['certificates'] })
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed')
    }
  }
=======
>>>>>>> origin/main

  const copyLink = (cert: any) => {
    const url = verifyUrl(cert.code)
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(() => toast.success('Verify link copied'))
    } else {
<<<<<<< HEAD
      prompt({
        title: 'Copy this link',
        description: 'Your browser blocked automatic copy. Select the text and copy it manually.',
        defaultValue: url,
        confirmLabel: 'Done',
        cancelLabel: 'Close',
      })
=======
      window.prompt('Copy this link:', url)
>>>>>>> origin/main
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
<<<<<<< HEAD
            <div key={c.id} className={`bg-white rounded-2xl shadow-sm p-5 border transition ${c.revoked_at ? 'border-red-300 opacity-80' : 'border-slate-200 hover:border-amber-300 hover:shadow-lg'}`} data-testid={`cert-${c.id}`}>
              {c.revoked_at && (
                <div className="mb-3 -mt-2 -mx-2 px-3 py-1.5 bg-red-50 border-b border-red-200 rounded-t-lg text-[11px] font-semibold text-red-700 uppercase tracking-wide flex items-center gap-1.5"
                  data-testid={`cert-revoked-banner-${c.id}`}>
                  <XCircle className="h-3.5 w-3.5" /> Revoked
                </div>
              )}
=======
            <div key={c.id} className="bg-white rounded-2xl shadow-sm p-5 border border-slate-200 hover:border-amber-300 hover:shadow-lg transition" data-testid={`cert-${c.id}`}>
>>>>>>> origin/main
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
<<<<<<< HEAD
                  <Linkedin className="h-3.5 w-3.5" /> Add to LinkedIn
                </button>
                <button onClick={() => copyShareLink(c)} data-testid={`cert-share-${c.id}`}
                  className="inline-flex items-center justify-center gap-1.5 text-xs bg-fuchsia-600 hover:bg-fuchsia-700 text-white px-3 py-2 rounded-lg font-semibold"
                  title="Get a shareable link with a rich preview card">
                  <Share2 className="h-3.5 w-3.5" /> Share card
                </button>
                <a href={verifyUrl(c.code)} target="_blank" rel="noreferrer"
                  data-testid={`cert-verify-${c.id}`}
                  className="col-span-2 inline-flex items-center justify-center gap-1.5 text-xs border border-emerald-300 text-emerald-700 hover:bg-emerald-50 px-3 py-2 rounded-lg font-semibold">
                  <ShieldCheck className="h-3.5 w-3.5" /> Verify
                </a>
                {isAdmin && !c.revoked_at && (
                  <button onClick={() => revokeCert(c)} data-testid={`cert-revoke-${c.id}`}
                    className="col-span-2 inline-flex items-center justify-center gap-1.5 text-xs border border-red-300 text-red-700 hover:bg-red-50 px-3 py-2 rounded-lg font-semibold">
                    <XCircle className="h-3.5 w-3.5" /> Revoke certificate
                  </button>
                )}
                {isAdmin && c.revoked_at && (
                  <button onClick={() => unrevokeCert(c)} data-testid={`cert-unrevoke-${c.id}`}
                    className="col-span-2 inline-flex items-center justify-center gap-1.5 text-xs border border-slate-300 text-slate-700 hover:bg-slate-50 px-3 py-2 rounded-lg font-semibold">
                    <RotateCcw className="h-3.5 w-3.5" /> Lift revocation
                  </button>
                )}
=======
                  <ExternalLink className="h-3.5 w-3.5" /> Add to LinkedIn
                </button>
                <a href={verifyUrl(c.code)} target="_blank" rel="noreferrer"
                  data-testid={`cert-verify-${c.id}`}
                  className="inline-flex items-center justify-center gap-1.5 text-xs border border-emerald-300 text-emerald-700 hover:bg-emerald-50 px-3 py-2 rounded-lg font-semibold">
                  <ShieldCheck className="h-3.5 w-3.5" /> Verify
                </a>
>>>>>>> origin/main
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

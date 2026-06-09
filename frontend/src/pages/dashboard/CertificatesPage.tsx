import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Award, Download, FileText } from 'lucide-react'
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

  return (
    <div className="p-8" data-testid="certificates-page">
      <div className="flex items-start justify-between mb-8">
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
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {certs.map(c => (
            <div key={c.id} className="bg-white rounded-2xl shadow-sm p-5 flex items-center gap-4" data-testid={`cert-${c.id}`}>
              <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center"><Award className="h-6 w-6 text-amber-500" /></div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-900 truncate">{c.course_title || 'Certificate'}</p>
                <p className="text-xs text-slate-500 mt-0.5">{c.type}</p>
                <p className="text-[11px] text-slate-400 mt-1 font-mono">/{c.code}</p>
              </div>
              <div className="flex flex-col gap-1.5">
                <button onClick={() => downloadPdf(c)} data-testid={`cert-download-${c.id}`}
                  className="inline-flex items-center gap-1.5 text-xs bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-lg font-medium">
                  <Download className="h-3.5 w-3.5" /> PDF
                </button>
                <a href={`/verify/${c.code}`} target="_blank" rel="noreferrer" className="text-xs text-indigo-600 hover:underline font-medium text-center">Verify</a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

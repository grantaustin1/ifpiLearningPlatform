import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Award } from 'lucide-react'

export default function CertificatesPage() {
  const { data: certs = [], isLoading } = useQuery<any[]>({
    queryKey: ['certificates'], queryFn: async () => (await api.get('/certificates')).data,
  })

  return (
    <div className="p-8" data-testid="certificates-page">
      <h1 className="text-2xl font-bold text-slate-900 font-display">Certificates</h1>
      <p className="text-slate-500 mt-1 mb-8">{isLoading ? 'Loading…' : `${certs.length} certificates`}</p>
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
              <a href={`/verify/${c.code}`} target="_blank" rel="noreferrer" className="text-xs text-indigo-600 hover:underline font-medium">Verify</a>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

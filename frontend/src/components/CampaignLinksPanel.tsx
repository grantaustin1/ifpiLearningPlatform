import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { BarChart3, Copy, Link2, Plus, QrCode, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from 'lib/utils'

const AttributionRow = ({ linkId }: { linkId: number }) => {
  const { data } = useQuery<any>({
    queryKey: ['campaign-attribution', linkId],
    queryFn: async () => (await api.get(`/admin/campaign-links/${linkId}/attribution`)).data,
  })
  if (!data) return <p className="text-xs text-slate-400 px-4 py-2">Loading…</p>
  const max = Math.max(1, ...(data.trend || []).map((t: any) => t.signups))
  return (
    <div className="px-4 pb-3" data-testid={`attribution-${linkId}`}>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Daily signups — last 30 days</p>
      <div className="flex items-end gap-[2px] h-14 mb-3" data-testid={`trend-chart-${linkId}`}>
        {(data.trend || []).map((t: any) => (
          <div key={t.date} title={`${t.date}: ${t.signups} signup${t.signups !== 1 ? 's' : ''}`}
            className={cn('flex-1 rounded-t-sm min-h-[2px]', t.signups > 0 ? 'bg-indigo-500 hover:bg-indigo-600' : 'bg-slate-100')}
            style={{ height: `${Math.max(4, (t.signups / max) * 100)}%` }} />
        ))}
      </div>
      {!data.breakdown.length ? <p className="text-xs text-slate-400">No signups yet.</p> : (
      <table className="w-full text-xs">
        <thead><tr className="text-slate-400 text-left"><th className="py-1 font-medium">utm_source</th><th className="font-medium">utm_medium</th><th className="font-medium text-right">Signups</th></tr></thead>
        <tbody>
          {data.breakdown.map((b: any, i: number) => (
            <tr key={i} className="border-t border-slate-50">
              <td className="py-1.5 text-slate-700">{b.utm_source}</td>
              <td className="text-slate-500">{b.utm_medium}</td>
              <td className="text-right font-semibold text-slate-700">{b.signups}</td>
            </tr>
          ))}
        </tbody>
      </table>
      )}
    </div>
  )
}

export const CampaignLinksPanel = () => {
  const qc = useQueryClient()
  const [showNew, setShowNew] = useState(false)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [courseId, setCourseId] = useState<string>('')

  const { data: links = [] } = useQuery<any[]>({
    queryKey: ['campaign-links'],
    queryFn: async () => (await api.get('/admin/campaign-links')).data,
  })
  const { data: courses = [] } = useQuery<any[]>({
    queryKey: ['courses'], queryFn: async () => (await api.get('/courses')).data,
  })

  const createMut = useMutation({
    mutationFn: async () => (await api.post('/admin/campaign-links', {
      name, auto_enroll_course_id: courseId ? Number(courseId) : null,
    })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign-links'] })
      toast.success('Campaign link created')
      setShowNew(false); setName(''); setCourseId('')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Could not create link'),
  })
  const toggleMut = useMutation({
    mutationFn: async (l: any) => (await api.patch(`/admin/campaign-links/${l.id}`, { is_active: !l.is_active })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['campaign-links'] }),
  })
  const deleteMut = useMutation({
    mutationFn: async (id: number) => (await api.delete(`/admin/campaign-links/${id}`)).data,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['campaign-links'] }); toast.success('Link deleted') },
  })

  const copyLink = (l: any) => {
    navigator.clipboard.writeText(`${window.location.origin}${l.join_path}`)
    toast.success('Link copied — share it anywhere')
  }

  const downloadQr = async (l: any) => {
    try {
      const res = await api.get(`/admin/campaign-links/${l.id}/qr`, {
        params: { base: window.location.origin }, responseType: 'blob',
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `qr-${l.name.replace(/[^a-zA-Z0-9_-]+/g, '-').toLowerCase()}.png`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('QR code downloaded — print-ready')
    } catch { toast.error('QR download failed') }
  }
  const published = courses.filter((c: any) => c.status === 'PUBLISHED')

  return (
    <div data-testid="campaign-links-panel">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-slate-500">Multi-use signup links for ads, social bios and QR codes. Each signup lands as a Learner and is counted per campaign.</p>
        <button onClick={() => setShowNew(true)} data-testid="new-campaign-link-btn"
          className="inline-flex items-center gap-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-2 rounded-lg font-medium whitespace-nowrap">
          <Plus className="h-4 w-4" /> New link
        </button>
      </div>

      {showNew && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs text-slate-500 block mb-1">Campaign name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Meta Ads July" data-testid="campaign-name-input"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white" />
          </div>
          <div className="min-w-[220px]">
            <label className="text-xs text-slate-500 block mb-1">Auto-enroll (optional)</label>
            <select value={courseId} onChange={(e) => setCourseId(e.target.value)} data-testid="campaign-course-select"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white">
              <option value="">No auto-enrollment</option>
              {published.map((c: any) => <option key={c.id} value={c.id}>{c.title}</option>)}
            </select>
          </div>
          <button onClick={() => name.trim() && createMut.mutate()} disabled={!name.trim()} data-testid="campaign-create-btn"
            className="bg-indigo-600 text-white text-sm px-4 py-2 rounded-lg font-medium disabled:opacity-50">Create</button>
          <button onClick={() => setShowNew(false)} className="text-sm text-slate-500 px-2 py-2">Cancel</button>
        </div>
      )}

      {links.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <Link2 className="h-10 w-10 mx-auto mb-3 text-slate-200" />
          No campaign links yet.
        </div>
      ) : (
        <div className="space-y-2">
          {links.map((l: any) => (
            <div key={l.id} className="bg-white border border-slate-100 rounded-xl" data-testid={`campaign-link-${l.id}`}>
              <div className="flex items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900 text-sm">{l.name}</p>
                  <p className="text-[11px] text-slate-400 truncate">{window.location.origin}{l.join_path}
                    {l.auto_enroll_course_title && <> · auto-enrolls <span className="text-slate-500">{l.auto_enroll_course_title}</span></>}
                  </p>
                </div>
                <span className="text-xs font-semibold text-slate-600 whitespace-nowrap" data-testid={`campaign-signups-${l.id}`}>{l.signup_count} signup{l.signup_count !== 1 ? 's' : ''}</span>
                <button onClick={() => setExpanded(expanded === l.id ? null : l.id)} data-testid={`campaign-attribution-btn-${l.id}`}
                  title="UTM attribution" className={cn('hover:text-indigo-600', expanded === l.id ? 'text-indigo-600' : 'text-slate-400')}>
                  <BarChart3 className="h-4 w-4" />
                </button>
                <button onClick={() => toggleMut.mutate(l)} data-testid={`campaign-toggle-${l.id}`}
                  className={cn('text-[11px] font-semibold px-2.5 py-1 rounded-full',
                    l.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-400')}>
                  {l.is_active ? 'Active' : 'Paused'}
                </button>
                <button onClick={() => copyLink(l)} data-testid={`campaign-copy-${l.id}`} className="text-slate-400 hover:text-indigo-600"><Copy className="h-4 w-4" /></button>
                <button onClick={() => downloadQr(l)} data-testid={`campaign-qr-${l.id}`} title="Download print-ready QR code" className="text-slate-400 hover:text-indigo-600"><QrCode className="h-4 w-4" /></button>
                <button onClick={() => window.confirm('Delete this campaign link?') && deleteMut.mutate(l.id)} data-testid={`campaign-delete-${l.id}`} className="text-slate-300 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
              </div>
              {expanded === l.id && <AttributionRow linkId={l.id} />}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Award, Download, ShieldCheck, ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from 'lib/utils'

const CELL: Record<string, { label: string; cls: string }> = {
  completed: { label: 'Completed', cls: 'bg-emerald-100 text-emerald-700' },
  rpl: { label: 'RPL', cls: 'bg-violet-100 text-violet-700' },
  in_progress: { label: 'In progress', cls: 'bg-sky-100 text-sky-700' },
  not_started: { label: '—', cls: 'bg-slate-50 text-slate-400' },
}

export default function AdminPathwaysPage() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const [tab, setTab] = useState(0)

  const { data: tracks = [], isLoading } = useQuery<any[]>({
    queryKey: ['pathways-admin'],
    queryFn: async () => (await api.get('/pathways/admin/completions')).data,
  })

  const rplMut = useMutation({
    mutationFn: async ({ user_id, course_id, revoke }: any) =>
      revoke
        ? (await api.delete(`/pathways/admin/rpl/${user_id}/${course_id}`)).data
        : (await api.post('/pathways/admin/rpl', { user_id, course_id })).data,
    onSuccess: (d: any, vars: any) => {
      qc.invalidateQueries({ queryKey: ['pathways-admin'] })
      if (vars.revoke) toast.success('RPL revoked')
      else if (d.qualifications_earned?.length)
        toast.success(`RPL granted — qualification awarded: ${d.qualifications_earned.join(', ')}`)
      else toast.success('RPL granted')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'RPL update failed'),
  })

  const downloadCsv = async () => {
    const res = await api.get('/pathways/admin/completions.csv', { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url; a.download = 'qualification-compliance.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  const t = tracks[tab]

  const onCell = (row: any, cell: any) => {
    if (cell.state === 'completed') return
    if (cell.state === 'rpl') {
      if (window.confirm(`Revoke RPL for ${row.name || row.email}?`))
        rplMut.mutate({ user_id: row.user_id, course_id: cell.course_id, revoke: true })
    } else if (window.confirm(`Grant RPL (mark module complete) for ${row.name || row.email}?`)) {
      rplMut.mutate({ user_id: row.user_id, course_id: cell.course_id })
    }
  }

  return (
    <div className="p-8" data-testid="admin-pathways-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <button onClick={() => nav('/pathways')} className="text-xs text-slate-400 hover:text-slate-600 inline-flex items-center gap-1 mb-1" data-testid="back-to-pathways-btn">
            <ArrowLeft className="h-3 w-3" /> Pathway map
          </button>
          <h1 className="text-2xl font-bold text-slate-900 font-display flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-violet-600" /> Track Compliance
          </h1>
          <p className="text-slate-500 mt-1 text-sm">Who's where on each qualification track. Click a cell to grant or revoke RPL (Recognition of Prior Learning).</p>
        </div>
        <button onClick={downloadCsv} data-testid="compliance-csv-btn"
          className="inline-flex items-center gap-2 text-sm bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-lg font-medium">
          <Download className="h-4 w-4" /> Export CSV
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16"><div className="w-7 h-7 border-4 border-violet-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : tracks.length === 0 ? (
        <p className="text-slate-500 py-16 text-center">No qualification tracks published.</p>
      ) : (
        <>
          <div className="flex gap-2 mb-4">
            {tracks.map((tr, i) => (
              <button key={tr.id} onClick={() => setTab(i)} data-testid={`track-tab-${tr.id}`}
                className={cn('px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                  i === tab ? 'bg-violet-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200')}>
                {tr.title}
              </button>
            ))}
          </div>

          {t && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-x-auto">
              <table className="w-full text-sm" data-testid="compliance-table">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
                    <th className="px-4 py-3 font-medium">Learner</th>
                    {t.courses.map((c: any) => (
                      <th key={c.course_id} className="px-3 py-3 font-medium max-w-[160px]">
                        <span className="line-clamp-2">{c.title}</span>
                      </th>
                    ))}
                    <th className="px-4 py-3 font-medium">Qualification</th>
                  </tr>
                </thead>
                <tbody>
                  {t.learners.map((row: any) => (
                    <tr key={row.user_id} className="border-b border-slate-50 hover:bg-slate-50/50" data-testid={`compliance-row-${row.user_id}`}>
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-900">{row.name || '—'}</p>
                        <p className="text-[11px] text-slate-400">{row.email}</p>
                      </td>
                      {row.cells.map((cell: any) => {
                        const m = CELL[cell.state]
                        return (
                          <td key={cell.course_id} className="px-3 py-3">
                            <button onClick={() => onCell(row, cell)}
                              data-testid={`cell-${row.user_id}-${cell.course_id}`}
                              title={cell.state === 'completed' ? 'Completed normally' : cell.state === 'rpl' ? 'Click to revoke RPL' : 'Click to grant RPL'}
                              className={cn('text-[11px] font-semibold px-2.5 py-1 rounded-full whitespace-nowrap', m.cls,
                                cell.state !== 'completed' && 'hover:ring-2 hover:ring-violet-300 cursor-pointer')}>
                              {m.label}{cell.state === 'in_progress' && ` ${cell.progress}%`}
                            </button>
                          </td>
                        )
                      })}
                      <td className="px-4 py-3">
                        {row.qualified ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700">
                            <Award className="h-3 w-3" /> {t.designation}
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-300">Not yet</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {t.learners.length === 0 && (
                    <tr><td colSpan={t.courses.length + 2} className="px-4 py-10 text-center text-slate-400">No learners in this organization yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}

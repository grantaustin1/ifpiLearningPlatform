import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Plus, Building2, Users, BookOpen, X, Send, ExternalLink, Search } from 'lucide-react'
import { toast } from 'sonner'
import { timeAgo } from 'lib/utils'

export default function AcademiesPage() {
  const qc = useQueryClient()
  const [show, setShow] = useState(false)
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sort, setSort] = useState('newest')

  const { data: rows = [], isLoading } = useQuery<any[]>({
    queryKey: ['academies', q, statusFilter, sort],
    queryFn: async () => (await api.get('/academies', {
      params: { q: q || undefined, status_filter: statusFilter || undefined, sort },
    })).data,
  })

  return (
    <div className="p-8" data-testid="academies-page">
      {show && <CreateModal onClose={() => setShow(false)} onCreated={() => { qc.invalidateQueries({ queryKey: ['academies'] }); setShow(false) }} />}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">Academies</h1>
          <p className="text-slate-500 mt-1">{isLoading ? 'Loading…' : `${rows.length} academies on the platform`}</p>
        </div>
        <button onClick={() => setShow(true)} data-testid="new-academy-btn"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg shadow-sm">
          <Plus className="h-4 w-4" /> New Academy
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-5">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search by name or slug…"
            data-testid="academies-search"
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/40" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} data-testid="academies-status-filter"
          className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white">
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="SUSPENDED">Suspended</option>
        </select>
        <select value={sort} onChange={e => setSort(e.target.value)} data-testid="academies-sort"
          className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white">
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="name">Name (A→Z)</option>
          <option value="users">Most users</option>
          <option value="courses">Most courses</option>
        </select>
        {(q || statusFilter || sort !== 'newest') && (
          <button onClick={() => { setQ(''); setStatusFilter(''); setSort('newest') }}
            className="text-xs text-slate-500 hover:text-slate-700">Clear</button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {rows.map((a: any) => (
          <div key={a.id} className="bg-white rounded-2xl shadow-sm p-5" data-testid={`academy-${a.id}`}>
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                   style={{ background: (a.primary_color || '#6366f1') + '20' }}>
                <Building2 className="h-5 w-5" style={{ color: a.primary_color || '#6366f1' }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-900 truncate">{a.name}</p>
                <p className="text-xs text-slate-400 font-mono">/{a.slug}</p>
              </div>
              <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${a.status === 'ACTIVE' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>{a.status}</span>
            </div>
            {a.theme_preset && (
              <span className="inline-block text-[10px] font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 mb-2">
                {a.theme_preset.replace(/_/g, ' ')}
              </span>
            )}
            <div className="flex items-center gap-4 text-xs text-slate-500 mb-3">
              <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {a.user_count} users</span>
              <span className="flex items-center gap-1"><BookOpen className="h-3.5 w-3.5" /> {a.course_count} courses</span>
              <span className="ml-auto">{timeAgo(a.created_at)}</span>
            </div>
            <a href={`/a/${a.slug}`} target="_blank" rel="noreferrer"
               data-testid={`academy-demo-${a.id}`}
               className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50 rounded-md px-2 py-1 -ml-2">
              <ExternalLink className="h-3.5 w-3.5" /> Demo this academy
            </a>
          </div>
        ))}
      </div>
    </div>
  )
}

function CreateModal({ onClose, onCreated }: any) {
  const [form, setForm] = useState({ name: '', slug: '', description: '', admin_email: '', admin_name: '' })
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setLoading(true)
    try {
      await api.post('/academies', form)
      toast.success(`Academy created — invitation sent to ${form.admin_email}`)
      onCreated()
    } catch (err: any) { toast.error(err?.response?.data?.detail || 'Failed'); setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" data-testid="academy-modal">
      <form onSubmit={submit} className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <h3 className="font-semibold">Create a new academy</h3>
          <button type="button" onClick={onClose}><X className="h-5 w-5 text-slate-400" /></button>
        </div>
        <div className="p-6 space-y-3">
          <Field label="Name *"><input required value={form.name} onChange={e => setForm({...form, name: e.target.value})} data-testid="academy-name" className={inp} /></Field>
          <Field label="URL slug *" help="Used in URLs: /a/<slug>"><input required value={form.slug} onChange={e => setForm({...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-')})} data-testid="academy-slug" className={`${inp} font-mono`} placeholder="ifpi-uk" /></Field>
          <Field label="Description"><textarea rows={2} value={form.description} onChange={e => setForm({...form, description: e.target.value})} className={inp} /></Field>
          <div className="border-t pt-3 mt-3">
            <p className="text-xs font-semibold text-slate-700 uppercase tracking-wide mb-2">Invite the first admin</p>
            <Field label="Admin email *"><input required type="email" value={form.admin_email} onChange={e => setForm({...form, admin_email: e.target.value})} data-testid="academy-admin-email" className={inp} /></Field>
            <Field label="Admin name"><input value={form.admin_name} onChange={e => setForm({...form, admin_name: e.target.value})} className={inp} /></Field>
          </div>
        </div>
        <div className="px-6 py-4 border-t flex justify-end gap-2 bg-slate-50">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-600">Cancel</button>
          <button type="submit" disabled={loading} data-testid="academy-submit"
            className="inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50">
            <Send className="h-3.5 w-3.5" /> {loading ? 'Creating…' : 'Create + invite admin'}
          </button>
        </div>
      </form>
    </div>
  )
}

const inp = "w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
function Field({ label, help, children }: any) { return <div><label className="block text-xs font-semibold text-slate-700 mb-1 uppercase tracking-wide">{label}</label>{children}{help && <p className="text-[11px] text-slate-400 mt-1">{help}</p>}</div> }

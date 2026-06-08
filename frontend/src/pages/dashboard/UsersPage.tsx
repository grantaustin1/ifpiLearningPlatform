import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Shield, BookOpen, Award, UserPlus, X, Mail, MoreHorizontal, Trash2, Send } from 'lucide-react'
import { toast } from 'sonner'
import { timeAgo } from 'lib/utils'

const INVITE_ROLES = ['INSTRUCTOR', 'ADMIN', 'BILLING_VIEWER', 'LEARNER']

export default function UsersPage() {
  const [tab, setTab] = useState<'users' | 'invitations'>('users')
  const [showInvite, setShowInvite] = useState(false)
  const qc = useQueryClient()

  const { data: users = [], isLoading } = useQuery<any[]>({
    queryKey: ['admin-users'], queryFn: async () => (await api.get('/admin/users')).data,
  })
  const { data: invites = [] } = useQuery<any[]>({
    queryKey: ['invitations'], queryFn: async () => (await api.get('/admin/invitations')).data,
  })

  const revokeMut = useMutation({
    mutationFn: async (id: number) => api.delete(`/admin/invitations/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['invitations'] }); toast.success('Invitation revoked') },
  })

  const learners = users.filter((u: any) => u.roles?.includes('LEARNER')).length
  const certs = users.reduce((a: number, u: any) => a + u.certificates, 0)
  const pendingInvites = invites.filter((i: any) => i.status === 'pending').length

  return (
    <div className="p-8" data-testid="users-page">
      {showInvite && <InviteModal onClose={() => setShowInvite(false)} onCreated={() => {
        qc.invalidateQueries({ queryKey: ['invitations'] })
        setShowInvite(false); setTab('invitations')
      }} />}

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">Users</h1>
          <p className="text-slate-500 mt-1">{isLoading ? 'Loading…' : `${users.length} members · ${pendingInvites} pending invitations`}</p>
        </div>
        <button onClick={() => setShowInvite(true)} data-testid="invite-user-btn"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg shadow-sm">
          <UserPlus className="h-4 w-4" /> Invite User
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: 'Total Users', value: users.length, icon: Shield, color: 'text-indigo-600', bg: 'bg-indigo-50' },
          { label: 'Learners', value: learners, icon: BookOpen, color: 'text-emerald-600', bg: 'bg-emerald-50' },
          { label: 'Certificates', value: certs, icon: Award, color: 'text-amber-600', bg: 'bg-amber-50' },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-2xl shadow-sm p-5 flex items-center gap-4">
            <div className={`p-2.5 rounded-xl ${s.bg}`}><s.icon className={`h-5 w-5 ${s.color}`} /></div>
            <div><p className="text-2xl font-bold text-slate-900">{s.value}</p><p className="text-xs text-slate-500 mt-1">{s.label}</p></div>
          </div>
        ))}
      </div>

      <div className="flex border-b border-slate-200 mb-4">
        {(['users', 'invitations'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} data-testid={`tab-${t}`}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${tab === t ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
            {t === 'users' ? `Members (${users.length})` : `Invitations (${invites.length})`}
          </button>
        ))}
      </div>

      {tab === 'users' ? (
        <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b"><tr>
              <th className="text-left px-6 py-3 font-medium text-slate-500">User</th>
              <th className="text-left px-6 py-3 font-medium text-slate-500">Role</th>
              <th className="text-right px-6 py-3 font-medium text-slate-500">XP</th>
              <th className="text-right px-6 py-3 font-medium text-slate-500">Enrolled</th>
              <th className="text-right px-6 py-3 font-medium text-slate-500">Completed</th>
              <th className="text-right px-6 py-3 font-medium text-slate-500">Certs</th>
            </tr></thead>
            <tbody className="divide-y">
              {users.map((u: any) => {
                const initials = (u.name ?? '?').split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
                return (
                  <tr key={u.id} data-testid={`user-row-${u.id}`}>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold">{initials}</div>
                        <div><p className="font-medium text-slate-900">{u.name ?? '(no name)'}</p><p className="text-xs text-slate-400">{u.email}</p></div>
                      </div>
                    </td>
                    <td className="px-6 py-4"><span className="text-xs font-medium px-2.5 py-1 rounded-full bg-slate-100 text-slate-600">{u.roles?.[0] || 'LEARNER'}</span></td>
                    <td className="px-6 py-4 text-right font-medium">{u.points}</td>
                    <td className="px-6 py-4 text-right text-slate-600">{u.enrollments}</td>
                    <td className="px-6 py-4 text-right text-slate-600">{u.completed}</td>
                    <td className="px-6 py-4 text-right text-slate-600">{u.certificates}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
          {invites.length === 0 ? (
            <p className="py-10 text-center text-slate-400 text-sm">No invitations yet — invite your first user.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b"><tr>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Email</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Role</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Status</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Sent</th>
                <th className="text-right px-6 py-3 font-medium text-slate-500"></th>
              </tr></thead>
              <tbody className="divide-y">
                {invites.map((i: any) => (
                  <tr key={i.id} data-testid={`invite-row-${i.id}`}>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2"><Mail className="h-4 w-4 text-slate-400" /> <span className="font-medium">{i.email}</span></div>
                      {i.name && <p className="text-xs text-slate-400 mt-0.5 ml-6">{i.name}</p>}
                    </td>
                    <td className="px-6 py-4"><span className="text-xs font-medium px-2.5 py-1 rounded-full bg-slate-100 text-slate-600">{i.role}</span></td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full ${
                        i.status === 'pending' ? 'bg-amber-100 text-amber-700' :
                        i.status === 'accepted' ? 'bg-emerald-100 text-emerald-700' :
                        'bg-slate-100 text-slate-500'
                      }`}>{i.status}</span>
                    </td>
                    <td className="px-6 py-4 text-slate-500 text-xs">{timeAgo(i.created_at)}</td>
                    <td className="px-6 py-4 text-right">
                      {i.status === 'pending' && (
                        <button onClick={() => revokeMut.mutate(i.id)} data-testid={`revoke-invite-${i.id}`}
                          className="text-xs text-red-600 hover:text-red-700">Revoke</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

function InviteModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [email, setEmail] = useState(''); const [name, setName] = useState('')
  const [role, setRole] = useState('INSTRUCTOR'); const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setLoading(true); setError('')
    try {
      await api.post('/admin/invitations', { email, name: name || undefined, role })
      toast.success('Invitation sent (queued in outbox)')
      onCreated()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not send invitation')
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" data-testid="invite-modal">
      <form onSubmit={submit} className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <h3 className="font-semibold text-slate-900">Invite a user</h3>
          <button type="button" onClick={onClose}><X className="h-5 w-5 text-slate-400" /></button>
        </div>
        <div className="p-6 space-y-4">
          {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">{error}</div>}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Email *</label>
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)} data-testid="invite-email"
              className="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Name (optional)</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)} data-testid="invite-name"
              className="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Role</label>
            <select value={role} onChange={e => setRole(e.target.value)} data-testid="invite-role"
              className="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-sm bg-white">
              {INVITE_ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
            <p className="text-[11px] text-slate-400 mt-1.5">The invite expires in 14 days. The recipient sets their own password.</p>
          </div>
        </div>
        <div className="px-6 py-4 border-t flex justify-end gap-2 bg-slate-50">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-600 rounded-lg hover:bg-slate-100">Cancel</button>
          <button type="submit" disabled={loading} data-testid="invite-submit"
            className="inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50">
            {loading ? 'Sending…' : <><Send className="h-3.5 w-3.5" /> Send invitation</>}
          </button>
        </div>
      </form>
    </div>
  )
}

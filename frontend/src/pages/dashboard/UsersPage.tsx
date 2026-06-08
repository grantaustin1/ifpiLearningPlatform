import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Shield, BookOpen, Award } from 'lucide-react'

export default function UsersPage() {
  const { data: users = [], isLoading } = useQuery<any[]>({
    queryKey: ['admin-users'], queryFn: async () => (await api.get('/admin/users')).data,
  })

  const learners = users.filter((u: any) => u.roles?.includes('LEARNER')).length
  const certs = users.reduce((a: number, u: any) => a + u.certificates, 0)
  const stats = [
    { label: 'Total Users',     value: users.length, icon: Shield, color: 'text-indigo-600',  bg: 'bg-indigo-50' },
    { label: 'Active Learners', value: learners,     icon: BookOpen, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Certificates',    value: certs,        icon: Award, color: 'text-amber-600',   bg: 'bg-amber-50' },
  ]

  return (
    <div className="p-8" data-testid="users-page">
      <h1 className="text-2xl font-bold text-slate-900 font-display">Users</h1>
      <p className="text-slate-500 mt-1 mb-6">{isLoading ? 'Loading…' : `${users.length} members`}</p>

      <div className="grid grid-cols-3 gap-4 mb-6">
        {stats.map(s => (
          <div key={s.label} className="bg-white rounded-2xl shadow-sm p-5 flex items-center gap-4">
            <div className={`p-2.5 rounded-xl ${s.bg}`}><s.icon className={`h-5 w-5 ${s.color}`} /></div>
            <div><p className="text-2xl font-bold text-slate-900">{s.value}</p><p className="text-xs text-slate-500 mt-1">{s.label}</p></div>
          </div>
        ))}
      </div>

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
    </div>
  )
}

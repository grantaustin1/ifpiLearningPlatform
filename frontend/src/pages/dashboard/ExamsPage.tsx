import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { Plus, ClipboardList, Clock, Users, CheckCircle, Eye } from 'lucide-react'
import { toast } from 'sonner'

export default function ExamsPage() {
  const { hasRole } = useAuth()
  const qc = useQueryClient()
  const isAdmin = hasRole('ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR')

  const { data: exams = [], isLoading } = useQuery<any[]>({
    queryKey: ['exams'], queryFn: async () => (await api.get('/exams')).data,
  })

  const createMut = useMutation({
    mutationFn: async () => (await api.post('/exams', {
      title: 'Untitled Exam', passing_score: 70, max_attempts: 3, is_published: false,
    })).data,
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ['exams'] }); toast.success('Exam created'); },
  })

  return (
    <div className="p-8" data-testid="exams-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">Exams</h1>
          <p className="text-slate-500 mt-1">{isLoading ? 'Loading…' : `${exams.length} exams total`}</p>
        </div>
        {isAdmin && (
          <button onClick={() => createMut.mutate()} data-testid="new-exam-btn"
            className="inline-flex items-center gap-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium">
            <Plus className="h-4 w-4" /> New Exam
          </button>
        )}
      </div>

      {isLoading ? <div className="flex items-center justify-center py-16"><div className="w-7 h-7 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div> :
       exams.length === 0 ? (
        <div className="text-center py-16 text-slate-400">No exams yet.</div>
      ) : (
        <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Exam</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Questions</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Attempts</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Time Limit</th>
                <th className="text-left px-6 py-3 font-medium text-slate-500">Status</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y">
              {exams.map(e => (
                <tr key={e.id} data-testid={`exam-row-${e.id}`}>
                  <td className="px-6 py-4 font-medium text-slate-900">{e.title}</td>
                  <td className="px-6 py-4"><span className="inline-flex items-center gap-1.5 text-slate-600"><ClipboardList className="h-3.5 w-3.5" /> {e.question_count}</span></td>
                  <td className="px-6 py-4"><span className="inline-flex items-center gap-1.5 text-slate-600"><Users className="h-3.5 w-3.5" /> {e.attempt_count}</span></td>
                  <td className="px-6 py-4">{e.time_limit_minutes ? <span className="inline-flex items-center gap-1.5 text-slate-600"><Clock className="h-3.5 w-3.5" /> {e.time_limit_minutes}m</span> : <span className="text-slate-400">—</span>}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full ${e.is_published ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                      <CheckCircle className="h-3 w-3" /> {e.is_published ? 'Published' : 'Draft'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link to={`/take/${e.id}`} className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700">
                      <Eye className="h-3.5 w-3.5" /> {isAdmin ? 'Preview' : 'Take'}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

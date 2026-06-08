import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { Plus, BookOpen, Layers, Clock, Users, ArrowRight, CheckCircle } from 'lucide-react'
import { toast } from 'sonner'
import { formatCurrency } from 'lib/utils'

export default function LearningPathsPage() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { hasRole } = useAuth()
  const isAdmin = hasRole('ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR')

  const { data: paths = [], isLoading } = useQuery<any[]>({
    queryKey: ['learning-paths'],
    queryFn: async () => (await api.get('/learning-paths')).data,
  })

  const createMut = useMutation({
    mutationFn: async () => (await api.post('/learning-paths', {
      title: 'Untitled Learning Path', cover_color: 'bg-violet-500',
    })).data,
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['learning-paths'] })
      toast.success('Learning path created')
      nav(`/learning-paths/${d.id}/edit`)
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Could not create'),
  })

  const enrollMut = useMutation({
    mutationFn: async (id: number) => (await api.post(`/learning-paths/${id}/enroll`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['learning-paths'] })
      toast.success('Enrolled — all path courses added to your dashboard')
    },
  })

  return (
    <div className="p-8" data-testid="paths-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">Learning Paths</h1>
          <p className="text-slate-500 mt-1">{isLoading ? 'Loading…' : `${paths.length} paths`}</p>
        </div>
        {isAdmin && (
          <button onClick={() => createMut.mutate()} data-testid="new-path-btn"
            className="inline-flex items-center gap-2 text-sm bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-lg font-medium">
            <Plus className="h-4 w-4" /> New Path
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16"><div className="w-7 h-7 border-4 border-violet-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : paths.length === 0 ? (
        <div className="text-center py-16">
          <Layers className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-500">{isAdmin ? 'No learning paths yet. Create one!' : 'No learning paths available yet.'}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {paths.map((p: any) => (
            <div key={p.id} className="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-shadow" data-testid={`path-card-${p.id}`}>
              <div className={`h-32 ${p.cover_color} flex items-end p-4`}>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${p.status === 'PUBLISHED' ? 'bg-white/20 text-white' : 'bg-black/30 text-white/80'}`}>{p.status}</span>
                  <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-white/20 text-white">{p.course_count} course{p.course_count !== 1 ? 's' : ''}</span>
                </div>
              </div>
              <div className="p-5">
                <h3 className="font-semibold text-slate-900">{p.title}</h3>
                {p.description && <p className="text-xs text-slate-500 mt-1.5 line-clamp-2">{p.description}</p>}
                <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                  <span className="flex items-center gap-1"><BookOpen className="h-3.5 w-3.5" /> {p.course_count}</span>
                  {p.estimated_hours && <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {p.estimated_hours}h</span>}
                  <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {p.enrollment_count}</span>
                </div>
                <div className="flex gap-2 mt-4">
                  {isAdmin ? (
                    <button onClick={() => nav(`/learning-paths/${p.id}/edit`)} className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs border border-slate-200 hover:border-slate-300 rounded-lg py-1.5 font-medium">
                      Manage <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  ) : p.status === 'PUBLISHED' && (
                    <button onClick={() => enrollMut.mutate(p.id)} disabled={enrollMut.isPending}
                      data-testid={`path-enroll-${p.id}`}
                      className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs bg-violet-600 hover:bg-violet-700 text-white rounded-lg py-1.5 font-medium disabled:opacity-50">
                      <CheckCircle className="h-3.5 w-3.5" /> Enrol in Path
                    </button>
                  )}
                  <p className="text-xs font-semibold self-center px-2">{p.price_cents === 0 ? 'Free' : formatCurrency(p.price_cents, p.currency)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

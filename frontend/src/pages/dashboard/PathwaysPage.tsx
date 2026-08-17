import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import {
  Award, CheckCircle2, Circle, Download, GraduationCap, Hammer, Lock,
  PlayCircle, Milestone, ShieldCheck,
} from 'lucide-react'
import { cn } from 'lib/utils'

const STATE_META: Record<string, { icon: any; label: string; cls: string }> = {
  completed: { icon: CheckCircle2, label: 'Completed', cls: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
  in_progress: { icon: PlayCircle, label: 'In progress', cls: 'text-sky-600 bg-sky-50 border-sky-200' },
  available: { icon: Circle, label: 'Ready to start', cls: 'text-slate-600 bg-white border-slate-200' },
  locked: { icon: Lock, label: 'Locked', cls: 'text-slate-400 bg-slate-50 border-slate-200' },
  coming_soon: { icon: Hammer, label: 'In production', cls: 'text-amber-600 bg-amber-50 border-amber-200' },
}

function StageCard({ stage, index, onOpen }: { stage: any; index: number; onOpen: () => void }) {
  const meta = STATE_META[stage.state] || STATE_META.available
  const Icon = meta.icon
  const clickable = stage.state === 'available' || stage.state === 'in_progress' || stage.state === 'completed'
  return (
    <div data-testid={`pathway-stage-${stage.course_id}`}
      onClick={clickable ? onOpen : undefined}
      className={cn('flex items-center gap-3 rounded-xl border p-3 transition-shadow', meta.cls,
        clickable && 'cursor-pointer hover:shadow-md')}>
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-white/70 border border-current/20 flex items-center justify-center text-xs font-bold">
        {index + 1}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-slate-900 truncate">{stage.title}</p>
        <p className="text-[11px] opacity-80 flex items-center gap-1">
          <Icon className="h-3 w-3" /> {meta.label}
          {stage.state === 'in_progress' && stage.progress > 0 && ` · ${stage.progress}%`}
        </p>
      </div>
      <Icon className="h-5 w-5 flex-shrink-0" />
    </div>
  )
}

export default function PathwaysPage() {
  const nav = useNavigate()
  const { hasRole } = useAuth()
  const isAdmin = hasRole('ADMIN', 'SUPER_ADMIN')
  const { data: tracks = [], isLoading } = useQuery<any[]>({
    queryKey: ['pathways-map'],
    queryFn: async () => (await api.get('/pathways/map')).data,
  })

  const sharedFirst = tracks.length > 1 &&
    tracks.every((t) => t.stages[0]?.course_id === tracks[0].stages[0]?.course_id)
  const gateway = sharedFirst ? tracks[0].stages[0] : null

  const openCourse = (s: any) => {
    if (s.state === 'available' || s.state === 'in_progress' || s.state === 'completed')
      nav(`/learn/${s.course_id}`)
  }

  return (
    <div className="p-8 max-w-5xl" data-testid="pathways-page">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-display flex items-center gap-2">
            <Milestone className="h-6 w-6 text-violet-600" /> Qualification Pathways
          </h1>
          <p className="text-slate-500 mt-1">Your route to an IFPI professional designation. Complete every module in a track to earn the qualification certificate.</p>
        </div>
        {isAdmin && (
          <button onClick={() => nav('/pathways/admin')} data-testid="pathways-admin-btn"
            className="inline-flex items-center gap-2 text-sm bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-lg font-medium whitespace-nowrap">
            <ShieldCheck className="h-4 w-4 text-violet-600" /> Track Compliance
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16"><div className="w-7 h-7 border-4 border-violet-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : tracks.length === 0 ? (
        <div className="text-center py-16">
          <GraduationCap className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-500">No qualification tracks published yet.</p>
        </div>
      ) : (
        <>
          {gateway && (
            <div className="mb-2" data-testid="pathway-gateway">
              <div className="max-w-md mx-auto">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 text-center mb-2">Shared Foundation — complete once</p>
                <StageCard stage={gateway} index={0} onOpen={() => openCourse(gateway)} />
              </div>
              <div className="flex justify-center gap-40 mt-1 mb-1">
                <div className="w-px h-6 bg-slate-300" />
                <div className="w-px h-6 bg-slate-300" />
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {tracks.map((t) => {
              const stages = gateway ? t.stages.slice(1) : t.stages
              const done = t.stages.filter((s: any) => s.state === 'completed').length
              const pct = t.stages.length ? Math.round((done / t.stages.length) * 100) : 0
              return (
                <div key={t.id} className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden" data-testid={`pathway-track-${t.id}`}>
                  <div className="p-5 border-b border-slate-100">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="font-semibold text-slate-900">{t.title}</h3>
                        <p className="text-xs text-slate-500 mt-0.5">{t.designation}</p>
                      </div>
                      {t.qualification_earned && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-full bg-emerald-100 text-emerald-700" data-testid={`qualification-earned-${t.id}`}>
                          <Award className="h-3 w-3" /> QUALIFIED
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-3 text-[11px] text-slate-500">
                      <span className="px-2 py-0.5 rounded-full bg-slate-100 font-medium">NQF Level {t.nqf_level}</span>
                      <span className="px-2 py-0.5 rounded-full bg-slate-100 font-medium">{t.total_credits} Credits</span>
                    </div>
                    <div className="mt-3">
                      <div className="flex justify-between text-[11px] text-slate-500 mb-1">
                        <span>{done}/{t.stages.length} modules</span><span>{pct}%</span>
                      </div>
                      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-violet-600 rounded-full transition-all" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  </div>
                  <div className="p-4 space-y-2">
                    {stages.map((s: any, i: number) => (
                      <div key={s.course_id}>
                        {i > 0 && <div className="w-px h-3 bg-slate-200 ml-7 mb-2" />}
                        <StageCard stage={s} index={gateway ? i + 1 : i} onOpen={() => openCourse(s)} />
                      </div>
                    ))}
                    <div className="flex items-center gap-3 rounded-xl border border-dashed p-3 mt-2 border-violet-200 bg-violet-50/50">
                      <GraduationCap className="h-5 w-5 text-violet-500 flex-shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-violet-900">{t.designation}</p>
                        <p className="text-[11px] text-violet-600">Qualification certificate on track completion</p>
                      </div>
                      {t.qualification_earned && t.certificate_id && (
                        <button onClick={() => nav('/certificates')} data-testid={`qualification-cert-btn-${t.id}`}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-violet-700 hover:text-violet-900">
                          <Download className="h-3.5 w-3.5" /> Certificate
                        </button>
                      )}
                    </div>
                  </div>
                  {t.unit_standards?.length > 0 && (
                    <div className="px-5 pb-4">
                      <details className="text-[11px] text-slate-400">
                        <summary className="cursor-pointer hover:text-slate-600">SAQA Unit Standards ({t.unit_standards.length})</summary>
                        <ul className="mt-1.5 space-y-1 list-disc list-inside">
                          {t.unit_standards.map((us: string) => <li key={us}>{us}</li>)}
                        </ul>
                      </details>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

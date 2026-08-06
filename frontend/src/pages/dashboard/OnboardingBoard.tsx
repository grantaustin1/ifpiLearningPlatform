/** Iter 30o — Onboarding checklist widget.
 *
 * Shown on admin dashboards until 100% complete (excluding optional
 * steps). Automatically hides itself once the org has finished setup.
 */
import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Link } from 'react-router-dom'
import { Check, Circle, ArrowRight, Rocket } from 'lucide-react'

type Step = { key: string; label: string; done: boolean; cta_path?: string; optional?: boolean }
type Checklist = { steps: Step[]; percent: number; completed: number; total: number }

export function OnboardingBoard() {
  const { data, isLoading } = useQuery<Checklist>({
    queryKey: ['onboarding-checklist'],
    queryFn: async () => (await api.get('/admin/onboarding/checklist')).data,
    staleTime: 30_000,
  })

  if (isLoading || !data) return null
  // Hide once fully done (100% of non-optional steps)
  if (data.percent >= 100) return null

  return (
    <div className="bg-gradient-to-br from-indigo-50 to-fuchsia-50 border border-indigo-100 rounded-2xl overflow-hidden"
         data-testid="onboarding-board">
      <div className="px-6 py-4 flex items-center gap-3 border-b border-indigo-100/60">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-600 to-fuchsia-600 flex items-center justify-center">
          <Rocket className="h-5 w-5 text-white" />
        </div>
        <div className="flex-1">
          <h2 className="text-sm font-semibold text-slate-900">Get your platform launch-ready</h2>
          <p className="text-xs text-slate-600">{data.completed} of {data.total} core steps done</p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-indigo-700">{data.percent}%</div>
        </div>
      </div>
      {/* Progress bar */}
      <div className="h-1.5 bg-indigo-100">
        <div className="h-full bg-gradient-to-r from-indigo-500 to-fuchsia-500 transition-all"
             style={{ width: `${data.percent}%` }} />
      </div>
      <ul className="divide-y divide-indigo-50" data-testid="onboarding-steps">
        {data.steps.map(s => (
          <li key={s.key} className="flex items-center gap-3 px-6 py-3 group"
              data-testid={`onboarding-step-${s.key}`}>
            {s.done
              ? <Check className="h-5 w-5 text-emerald-500 flex-shrink-0" />
              : <Circle className="h-5 w-5 text-slate-300 flex-shrink-0" />}
            <span className={`flex-1 text-sm ${s.done ? 'text-slate-500 line-through' : 'text-slate-800 font-medium'}`}>
              {s.label}
              {s.optional && (
                <span className="text-[10px] font-semibold ml-2 px-1.5 py-0.5 rounded bg-slate-200 text-slate-600 uppercase">Optional</span>
              )}
            </span>
            {!s.done && s.cta_path && (
              <Link to={s.cta_path}
                    data-testid={`onboarding-cta-${s.key}`}
                    className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 opacity-70 group-hover:opacity-100 inline-flex items-center gap-1">
                Start <ArrowRight className="h-3 w-3" />
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

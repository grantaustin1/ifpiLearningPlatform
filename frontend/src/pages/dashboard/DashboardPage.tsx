import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Link } from 'react-router-dom'
import { BookOpen, ClipboardList, Users, Award, ArrowRight, Plus, Sparkles, TrendingUp } from 'lucide-react'
import { timeAgo } from 'lib/utils'
import { MembersNeedingActionWidget } from './MembersNeedingActionWidget'
import { OnboardingBoard } from './OnboardingBoard'
import { DocsEngagementTile } from './DocsEngagementTile'
import { WeeklyEnrollmentsCard } from './WeeklyEnrollmentsCard'

export default function DashboardPage() {
  const { data: analytics, isLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: async () => (await api.get('/admin/analytics')).data,
  })

  if (isLoading) return <Spinner />
  if (!analytics) return <div className="p-8 text-slate-400">Could not load analytics.</div>

  const stats = [
    { label: 'Courses',      value: analytics.total_courses,      icon: BookOpen,      bg: 'bg-blue-50',    text: 'text-blue-600',    href: '/courses' },
    { label: 'Active Learners', value: analytics.total_learners,  icon: Users,         bg: 'bg-emerald-50', text: 'text-emerald-600', href: '/users' },
    { label: 'Exam Attempts',value: analytics.total_exam_attempts,icon: ClipboardList, bg: 'bg-violet-50',  text: 'text-violet-600',  href: '/exams' },
    { label: 'Certificates', value: analytics.total_certificates, icon: Award,         bg: 'bg-amber-50',   text: 'text-amber-600',   href: '/certificates' },
  ]
  const actions = [
    { href: '/courses',  label: 'New Course',  icon: BookOpen, color: 'bg-blue-600 hover:bg-blue-700' },
    { href: '/exams',    label: 'New Exam',    icon: ClipboardList, color: 'bg-violet-600 hover:bg-violet-700' },
    { href: '/users',    label: 'Manage Users',icon: Users, color: 'bg-emerald-600 hover:bg-emerald-700' },
    { href: '/reports',  label: 'Reports',     icon: TrendingUp, color: 'bg-amber-500 hover:bg-amber-600' },
  ]

  return (
    <div className="p-6 lg:p-8 space-y-8" data-testid="dashboard-page">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="h-4 w-4 text-indigo-500" />
            <p className="text-xs font-medium text-indigo-500 uppercase tracking-widest">Overview</p>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight font-display">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Live platform metrics</p>
        </div>
        <Link to="/courses" data-testid="dashboard-new-course"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2.5 rounded-xl shadow-md shadow-indigo-200 transition-all">
          <Plus className="h-4 w-4" /> New Course
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        {stats.map(s => (
          <Link key={s.label} to={s.href}
            className="bg-white rounded-2xl p-5 card-glow hover:shadow-md hover:-translate-y-0.5 transition-all">
            <div className="flex items-start justify-between mb-4">
              <div className={`w-10 h-10 rounded-xl ${s.bg} flex items-center justify-center`}><s.icon className={`h-5 w-5 ${s.text}`} /></div>
              <ArrowRight className="h-4 w-4 text-slate-300" />
            </div>
            <p className="text-2xl font-bold text-slate-900 tracking-tight">{s.value.toLocaleString()}</p>
            <p className="text-xs text-slate-500 mt-0.5 font-medium">{s.label}</p>
          </Link>
        ))}
      </div>

      <OnboardingBoard />

      <div className="grid xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2">
          <MembersNeedingActionWidget />
        </div>
        <div className="space-y-5">
          <DocsEngagementTile />
          <div className="bg-white rounded-2xl card-glow p-5">
            <h2 className="text-sm font-semibold text-slate-800 mb-4">Quick Actions</h2>
            <div className="grid grid-cols-2 gap-2">
              {actions.map(a => (
                <Link key={a.href} to={a.href}
                  className={`flex flex-col items-center gap-2 ${a.color} text-white text-xs font-semibold py-4 rounded-xl shadow transition-all hover:-translate-y-0.5`}>
                  <a.icon className="h-5 w-5" /> {a.label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2 bg-white rounded-2xl card-glow overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100"><h2 className="text-sm font-semibold text-slate-800">Recent Activity</h2></div>
          <div className="divide-y divide-slate-50">
            {analytics.recent_activity?.length === 0 ? (
              <p className="text-sm text-slate-400 px-6 py-8 text-center">No activity yet.</p>
            ) : analytics.recent_activity?.map((a: any, i: number) => (
              <div key={i} className="flex items-center gap-4 px-6 py-3.5 hover:bg-slate-50">
                <div className="w-2 h-2 rounded-full bg-indigo-500 flex-shrink-0" />
                <p className="text-sm text-slate-600 flex-1">
                  <span className="font-medium text-slate-900">{a.user_name}</span> enrolled in{' '}
                  <span className="font-medium text-slate-700">{a.course_title}</span>
                </p>
                <span className="text-[11px] text-slate-400">{timeAgo(a.enrolled_at)}</span>
              </div>
            ))}
          </div>
        </div>
        <WeeklyEnrollmentsCard />
      </div>
    </div>
  )
}

function Spinner() {
  return <div className="flex items-center justify-center h-64">
    <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
  </div>
}

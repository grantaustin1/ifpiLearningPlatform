"use client"

import { useState, useEffect } from "react"
import {
  Users, BookOpen, Award, BarChart3, TrendingUp,
  CheckCircle, ClipboardList, RefreshCw,
} from "lucide-react"

interface Overview {
  totalLearners: number; totalInstructors: number; totalAdmins: number
  totalCourses: number; totalEnrollments: number; completionRate: number
  avgExamScore: number; totalExamAttempts: number; totalCertificates: number
}
interface MonthBucket { month: string; count: number }
interface TopCourse { id: string; title: string; total: number; completed: number; rate: number }
interface Activity { userName: string; courseTitle: string; status: string; progress: number; enrolledAt: string }

const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

function timeAgo(iso: string) {
  const d = new Date(iso)
  const s = Math.floor((Date.now() - d.getTime()) / 1000)
  if (s < 60) return "just now"
  const m = Math.floor(s / 60); if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function StatCard({ label, value, sub, icon: Icon, color, bg }: {
  label: string; value: string | number; sub?: string
  icon: React.ElementType; color: string; bg: string
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex items-start gap-4">
      <div className={`${bg} p-2.5 rounded-xl flex-shrink-0`}>
        <Icon className={`h-5 w-5 ${color}`} />
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-900 leading-none">{value}</p>
        <p className="text-sm text-slate-500 mt-1 leading-tight">{label}</p>
        {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

function BarChart({ data }: { data: MonthBucket[] }) {
  const max = Math.max(...data.map(d => d.count), 1)
  return (
    <div className="flex items-end gap-2 h-32 w-full">
      {data.map((d, i) => {
        const label = MONTH_NAMES[new Date(d.month).getUTCMonth()] ?? ""
        const pct = Math.max((d.count / max) * 100, 2)
        return (
          <div key={i} className="flex-1 flex flex-col items-center gap-1 group">
            <span className="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">
              {d.count}
            </span>
            <div
              className="w-full bg-indigo-500 rounded-t-md transition-all duration-500 hover:bg-indigo-600"
              style={{ height: `${pct}%` }}
              title={`${label}: ${d.count}`}
            />
            <span className="text-[10px] text-slate-400">{label}</span>
          </div>
        )
      })}
    </div>
  )
}

function DonutRing({ pct, color, label }: { pct: number; color: string; label: string }) {
  const r = 40
  const circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ
  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#e5e7eb" strokeWidth="12" />
        <circle
          cx="50" cy="50" r={r} fill="none"
          stroke={color} strokeWidth="12"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
        />
        <text x="50" y="50" textAnchor="middle" dominantBaseline="central"
          className="text-lg font-bold" fill="#0f172a" fontSize="18" fontWeight="700">
          {pct}%
        </text>
      </svg>
      <span className="text-xs text-slate-500">{label}</span>
    </div>
  )
}

const STATUS_COLOR: Record<string, string> = {
  COMPLETED: "bg-emerald-100 text-emerald-700",
  IN_PROGRESS: "bg-indigo-100 text-indigo-700",
  NOT_STARTED: "bg-slate-100 text-slate-500",
}

export default function ReportsPage() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [monthly, setMonthly] = useState<MonthBucket[]>([])
  const [topCourses, setTopCourses] = useState<TopCourse[]>([])
  const [activity, setActivity] = useState<Activity[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = async (quiet = false) => {
    if (!quiet) setLoading(true)
    else setRefreshing(true)
    try {
      const res = await fetch("/api/admin/analytics")
      if (!res.ok) throw new Error("Failed")
      const d = await res.json()
      setOverview(d.overview)
      setMonthly(d.monthlyEnrollments ?? [])
      setTopCourses(d.topCourses ?? [])
      setActivity(d.recentActivity ?? [])
    } catch {}
    setLoading(false)
    setRefreshing(false)
  }

  useEffect(() => { load() }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (!overview) return (
    <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
      Failed to load analytics.
    </div>
  )

  const totalUsers = overview.totalLearners + overview.totalInstructors + overview.totalAdmins

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
            <BarChart3 className="h-5 w-5 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Analytics</h1>
            <p className="text-sm text-slate-500 mt-0.5">Platform overview and learner progress</p>
          </div>
        </div>
        <button
          onClick={() => load(true)}
          disabled={refreshing}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Learners" value={overview.totalLearners.toLocaleString()} icon={Users} color="text-indigo-600" bg="bg-indigo-50" />
        <StatCard label="Courses" value={overview.totalCourses.toLocaleString()} icon={BookOpen} color="text-violet-600" bg="bg-violet-50" />
        <StatCard label="Certificates Issued" value={overview.totalCertificates.toLocaleString()} icon={Award} color="text-amber-600" bg="bg-amber-50" />
        <StatCard label="Exam Attempts" value={overview.totalExamAttempts.toLocaleString()} sub={`Avg score: ${overview.avgExamScore}%`} icon={ClipboardList} color="text-emerald-600" bg="bg-emerald-50" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Monthly enrollments bar */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-800">Monthly Enrollments</h2>
              <p className="text-xs text-slate-400 mt-0.5">Last 6 months</p>
            </div>
            <TrendingUp className="h-4 w-4 text-slate-300" />
          </div>
          {monthly.length > 0
            ? <BarChart data={monthly} />
            : <div className="h-32 flex items-center justify-center text-sm text-slate-300">No enrollment data yet</div>
          }
        </div>

        {/* Donut stats */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
          <h2 className="text-sm font-semibold text-slate-800 mb-4">Completion & Score</h2>
          <div className="flex justify-around items-center h-32">
            <DonutRing pct={overview.completionRate} color="#6366f1" label="Completion rate" />
            <DonutRing pct={overview.avgExamScore} color="#10b981" label="Avg exam score" />
          </div>
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Top courses */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-50">
            <h2 className="text-sm font-semibold text-slate-800">Top Courses by Enrollment</h2>
          </div>
          <div className="divide-y divide-slate-50">
            {topCourses.length === 0 ? (
              <div className="py-10 text-center text-sm text-slate-300">No courses yet</div>
            ) : topCourses.map(c => (
              <div key={c.id} className="px-5 py-3.5 flex items-center gap-3 hover:bg-slate-50 transition-colors">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{c.title}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{c.total} enrolled · {c.completed} completed</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <div className="w-20 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${c.rate}%` }} />
                  </div>
                  <span className="text-xs font-semibold text-slate-700 w-9 text-right">{c.rate}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* User breakdown + recent activity */}
        <div className="space-y-4">
          {/* User breakdown */}
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
            <h2 className="text-sm font-semibold text-slate-800 mb-3">Users</h2>
            <div className="space-y-2">
              {[
                { label: "Learners", count: overview.totalLearners, color: "bg-indigo-500" },
                { label: "Instructors", count: overview.totalInstructors, color: "bg-violet-500" },
                { label: "Admins", count: overview.totalAdmins, color: "bg-slate-400" },
              ].map(item => (
                <div key={item.label} className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 w-20 flex-shrink-0">{item.label}</span>
                  <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${item.color} rounded-full`}
                      style={{ width: totalUsers > 0 ? `${(item.count / totalUsers) * 100}%` : "0%" }}
                    />
                  </div>
                  <span className="text-xs font-semibold text-slate-700 w-6 text-right">{item.count}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Recent activity */}
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-50">
              <h2 className="text-sm font-semibold text-slate-800">Recent Enrollments</h2>
            </div>
            <div className="divide-y divide-slate-50 max-h-52 overflow-y-auto">
              {activity.length === 0 ? (
                <div className="py-6 text-center text-xs text-slate-300">No activity yet</div>
              ) : activity.map((a, i) => (
                <div key={i} className="px-4 py-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-700 truncate">{a.userName}</p>
                      <p className="text-[11px] text-slate-400 truncate mt-0.5">{a.courseTitle}</p>
                    </div>
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full flex-shrink-0 ${STATUS_COLOR[a.status] ?? "bg-slate-100 text-slate-500"}`}>
                      {a.status.replace("_", " ")}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-300 mt-1">{timeAgo(a.enrolledAt)}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

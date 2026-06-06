import { auth } from "@/lib/auth"
import { redirect } from "next/navigation"
import Link from "next/link"
import {
  BookOpen, ClipboardList, Users, Award, TrendingUp,
  Plus, ArrowRight, CheckCircle, Clock, Sparkles,
} from "lucide-react"

const stats = [
  {
    label: "Total Courses",
    value: "12",
    change: "+2 this month",
    icon: BookOpen,
    gradient: "from-blue-500 to-indigo-600",
    bg: "bg-blue-50",
    text: "text-blue-600",
    glow: "card-glow-blue",
  },
  {
    label: "Active Learners",
    value: "248",
    change: "+18 this week",
    icon: Users,
    gradient: "from-emerald-400 to-teal-600",
    bg: "bg-emerald-50",
    text: "text-emerald-600",
    glow: "card-glow-green",
  },
  {
    label: "Exams Completed",
    value: "1,024",
    change: "+86 this week",
    icon: ClipboardList,
    gradient: "from-violet-500 to-purple-700",
    bg: "bg-violet-50",
    text: "text-violet-600",
    glow: "card-glow-purple",
  },
  {
    label: "Certificates Issued",
    value: "189",
    change: "+12 this month",
    icon: Award,
    gradient: "from-amber-400 to-orange-500",
    bg: "bg-amber-50",
    text: "text-amber-600",
    glow: "card-glow-amber",
  },
]

const recentActivity = [
  { user: "Sarah Johnson", action: "Completed", item: "Compliance Training 2024", time: "2m ago", type: "complete" },
  { user: "Mike Peters",   action: "Passed",    item: "Financial Regulations Exam", time: "15m ago", type: "pass" },
  { user: "Anna Lee",      action: "Enrolled in", item: "IFPI Fundamentals Course", time: "1h ago", type: "enroll" },
  { user: "David Chen",    action: "Started",   item: "Advanced Copyright Law", time: "2h ago", type: "start" },
  { user: "Emma Wilson",   action: "Received certificate for", item: "Music Industry Basics", time: "3h ago", type: "cert" },
]

const quickActions = [
  { href: "/courses/new", label: "New Course",  icon: BookOpen,      color: "bg-blue-600 hover:bg-blue-700",   shadow: "shadow-blue-200" },
  { href: "/exams/new",   label: "New Exam",    icon: ClipboardList, color: "bg-violet-600 hover:bg-violet-700", shadow: "shadow-violet-200" },
  { href: "/users",       label: "Add Learners", icon: Users,        color: "bg-emerald-600 hover:bg-emerald-700", shadow: "shadow-emerald-200" },
  { href: "/reports",     label: "Reports",     icon: TrendingUp,    color: "bg-amber-500 hover:bg-amber-600",  shadow: "shadow-amber-200" },
]

// Sparkline bars — mock weekly data
const completionData = [42, 58, 51, 67, 73, 71, 78]

export default async function DashboardPage() {
  const session = await auth()
  if (!session || session.user.role !== "ADMIN") redirect("/courses")
  return (
    <div className="p-6 lg:p-8 space-y-8">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="h-4 w-4 text-indigo-500" />
            <p className="text-xs font-medium text-indigo-500 uppercase tracking-widest">Overview</p>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Good morning! Here's what's happening today.</p>
        </div>
        <Link
          href="/courses/new"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2.5 rounded-xl shadow-md shadow-indigo-200 transition-all hover:shadow-lg hover:shadow-indigo-200 hover:-translate-y-0.5"
        >
          <Plus className="h-4 w-4" /> New Course
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        {stats.map(stat => (
          <div key={stat.label} className={`bg-white rounded-2xl p-5 ${stat.glow} border border-transparent`}>
            <div className="flex items-start justify-between mb-4">
              <div className={`w-10 h-10 rounded-xl ${stat.bg} flex items-center justify-center`}>
                <stat.icon className={`h-5 w-5 ${stat.text}`} />
              </div>
              <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
                {stat.change}
              </span>
            </div>
            <p className="text-2xl font-bold text-slate-900 tracking-tight">{stat.value}</p>
            <p className="text-xs text-slate-500 mt-0.5 font-medium">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Body */}
      <div className="grid xl:grid-cols-3 gap-5">

        {/* Recent Activity */}
        <div className="xl:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
            <h2 className="text-sm font-semibold text-slate-800">Recent Activity</h2>
            <Link href="/reports" className="text-xs font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y divide-slate-50">
            {recentActivity.map((item, i) => (
              <div key={i} className="flex items-center gap-4 px-6 py-3.5 hover:bg-slate-50/50 transition-colors">
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 ${
                  item.type === "complete" ? "bg-emerald-100" :
                  item.type === "pass"     ? "bg-blue-100"    :
                  item.type === "cert"     ? "bg-amber-100"   : "bg-slate-100"
                }`}>
                  {item.type === "complete" ? <CheckCircle className="h-3.5 w-3.5 text-emerald-600" /> :
                   item.type === "pass"     ? <CheckCircle className="h-3.5 w-3.5 text-blue-600" />   :
                   item.type === "cert"     ? <Award        className="h-3.5 w-3.5 text-amber-600" />  :
                                             <Clock        className="h-3.5 w-3.5 text-slate-500" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-700">
                    <span className="font-semibold">{item.user}</span>
                    {" "}<span className="text-slate-500">{item.action}</span>{" "}
                    <span className="text-indigo-600 font-medium">{item.item}</span>
                  </p>
                </div>
                <span className="text-xs text-slate-400 whitespace-nowrap">{item.time}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-5">

          {/* Quick Actions */}
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
            <h2 className="text-sm font-semibold text-slate-800 mb-4">Quick Actions</h2>
            <div className="grid grid-cols-2 gap-2">
              {quickActions.map(action => (
                <Link
                  key={action.href}
                  href={action.href}
                  className={`flex flex-col items-center justify-center gap-1.5 rounded-xl py-3.5 text-white ${action.color} shadow-md ${action.shadow} hover:shadow-lg transition-all hover:-translate-y-0.5`}
                >
                  <action.icon className="h-5 w-5" />
                  <span className="text-xs font-semibold">{action.label}</span>
                </Link>
              ))}
            </div>
          </div>

          {/* Completion Rate */}
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
            <div className="flex items-start justify-between mb-1">
              <h2 className="text-sm font-semibold text-slate-800">Completion Rate</h2>
              <span className="text-xs text-emerald-600 font-medium bg-emerald-50 px-2 py-0.5 rounded-full">+5%</span>
            </div>
            <p className="text-xs text-slate-400 mb-4">This month</p>
            <div className="flex items-end gap-1.5 h-14 mb-3">
              {completionData.map((v, i) => (
                <div key={i} className="flex-1 flex items-end">
                  <div
                    className={`w-full rounded-sm transition-all ${i === completionData.length - 1 ? "bg-indigo-500" : "bg-indigo-100"}`}
                    style={{ height: `${(v / 100) * 56}px` }}
                  />
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between">
              <p className="text-3xl font-bold text-slate-900 tracking-tight">78%</p>
              <p className="text-xs text-slate-400">7-day trend</p>
            </div>
            <div className="mt-3 h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-1.5 bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full" style={{ width: "78%" }} />
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}

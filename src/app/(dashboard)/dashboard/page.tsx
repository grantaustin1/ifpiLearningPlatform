import { auth } from "@/lib/auth"
import { redirect } from "next/navigation"
import Link from "next/link"
import { prisma } from "@/lib/prisma"
import {
  BookOpen, ClipboardList, Users, Award, TrendingUp,
  Plus, ArrowRight, CheckCircle, Sparkles,
} from "lucide-react"

export default async function DashboardPage() {
  const session = await auth()
  if (!session || !["ADMIN", "SUPER_ADMIN"].includes(session.user.role)) redirect("/courses")

  // ── Live KPI counts ────────────────────────────────────────────────────────
  const [courseCount, learnerCount, examCount, certCount] = await Promise.all([
    prisma.course.count({ where: { isPublished: true } }),
    prisma.user.count({ where: { role: "LEARNER" } }),
    prisma.examAttempt.count({ where: { completedAt: { not: null } } }),
    prisma.certificate.count(),
  ])

  const stats = [
    {
      label: "Published Courses", value: courseCount.toLocaleString(),
      icon: BookOpen, gradient: "from-blue-500 to-indigo-600",
      bg: "bg-blue-50", text: "text-blue-600", glow: "card-glow-blue", href: "/courses",
    },
    {
      label: "Active Learners", value: learnerCount.toLocaleString(),
      icon: Users, gradient: "from-emerald-400 to-teal-600",
      bg: "bg-emerald-50", text: "text-emerald-600", glow: "card-glow-green", href: "/users",
    },
    {
      label: "Exams Completed", value: examCount.toLocaleString(),
      icon: ClipboardList, gradient: "from-violet-500 to-purple-700",
      bg: "bg-violet-50", text: "text-violet-600", glow: "card-glow-purple", href: "/exams",
    },
    {
      label: "Certificates Issued", value: certCount.toLocaleString(),
      icon: Award, gradient: "from-amber-400 to-orange-500",
      bg: "bg-amber-50", text: "text-amber-600", glow: "card-glow-amber", href: "/certificates",
    },
  ]

  // ── Real recent activity ────────────────────────────────────────────────────
  const [recentEnrollments, recentAttempts, recentCerts] = await Promise.all([
    prisma.enrollment.findMany({
      take: 3, orderBy: { enrolledAt: "desc" },
      include: {
        user: { select: { id: true, name: true } },
        course: { select: { id: true, title: true } },
      },
    }),
    prisma.examAttempt.findMany({
      where: { completedAt: { not: null } },
      take: 3, orderBy: { completedAt: "desc" },
      include: {
        user: { select: { id: true, name: true } },
        exam: { select: { id: true, title: true } },
      },
    }),
    prisma.certificate.findMany({
      take: 2, orderBy: { issuedAt: "desc" },
      include: {
        user: { select: { id: true, name: true } },
        course: { select: { id: true, title: true } },
      },
    }),
  ])

  type Activity = {
    key: string; userName: string; userId: string
    action: string; item: string; itemHref: string
    time: Date; type: "enroll" | "pass" | "fail" | "cert"
  }

  const activity: Activity[] = [
    ...recentEnrollments.map(e => ({
      key: `enroll-${e.id}`, userName: e.user.name ?? "Learner", userId: e.user.id,
      action: "enrolled in", item: e.course.title, itemHref: `/courses/${e.course.id}/edit`,
      time: e.enrolledAt, type: "enroll" as const,
    })),
    ...recentAttempts.map(a => ({
      key: `attempt-${a.id}`, userName: a.user.name ?? "Learner", userId: a.user.id,
      action: a.passed ? "passed" : "attempted", item: a.exam.title, itemHref: `/exams/${a.exam.id}`,
      time: a.completedAt!, type: a.passed ? "pass" as const : "fail" as const,
    })),
    ...recentCerts.map(c => ({
      key: `cert-${c.id}`, userName: c.user.name ?? "Learner", userId: c.user.id,
      action: "received certificate for", item: c.course?.title ?? "course", itemHref: `/certificates`,
      time: c.issuedAt, type: "cert" as const,
    })),
  ].sort((a, b) => b.time.getTime() - a.time.getTime()).slice(0, 7)

  const activityDot: Record<string, string> = {
    enroll: "bg-blue-500", pass: "bg-emerald-500", fail: "bg-red-400", cert: "bg-amber-500",
  }

  function timeAgo(date: Date) {
    const diff = Date.now() - date.getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return "just now"
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    return `${Math.floor(hrs / 24)}d ago`
  }

  const quickActions = [
    { href: "/courses/new",    label: "New Course",   icon: BookOpen,      color: "bg-blue-600 hover:bg-blue-700",     shadow: "shadow-blue-200" },
    { href: "/exams/new",      label: "New Exam",     icon: ClipboardList, color: "bg-violet-600 hover:bg-violet-700", shadow: "shadow-violet-200" },
    { href: "/users",          label: "Add Learners", icon: Users,         color: "bg-emerald-600 hover:bg-emerald-700", shadow: "shadow-emerald-200" },
    { href: "/reports",        label: "Reports",      icon: TrendingUp,    color: "bg-amber-500 hover:bg-amber-600",   shadow: "shadow-amber-200" },
  ]

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
          <p className="text-sm text-slate-500 mt-1">Live platform metrics</p>
        </div>
        <Link href="/courses/new"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2.5 rounded-xl shadow-md shadow-indigo-200 transition-all hover:shadow-lg hover:-translate-y-0.5">
          <Plus className="h-4 w-4" /> New Course
        </Link>
      </div>

      {/* KPI Tiles — each links to the relevant list page */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        {stats.map(stat => (
          <Link key={stat.label} href={stat.href}
            className={`bg-white rounded-2xl p-5 ${stat.glow} border border-transparent hover:shadow-md hover:-translate-y-0.5 transition-all cursor-pointer block`}>
            <div className="flex items-start justify-between mb-4">
              <div className={`w-10 h-10 rounded-xl ${stat.bg} flex items-center justify-center`}>
                <stat.icon className={`h-5 w-5 ${stat.text}`} />
              </div>
              <ArrowRight className="h-4 w-4 text-slate-300 group-hover:text-indigo-400" />
            </div>
            <p className="text-2xl font-bold text-slate-900 tracking-tight">{stat.value}</p>
            <p className="text-xs text-slate-500 mt-0.5 font-medium">{stat.label}</p>
          </Link>
        ))}
      </div>

      {/* Body */}
      <div className="grid xl:grid-cols-3 gap-5">
        {/* Real Recent Activity */}
        <div className="xl:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
            <h2 className="text-sm font-semibold text-slate-800">Recent Activity</h2>
            <Link href="/reports" className="text-xs font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y divide-slate-50">
            {activity.length === 0 ? (
              <p className="text-sm text-slate-400 px-6 py-8 text-center">No activity yet — enrolments and completions will appear here.</p>
            ) : activity.map(a => (
              <div key={a.key} className="flex items-start gap-4 px-6 py-3.5 hover:bg-slate-50 transition-colors">
                <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${activityDot[a.type]}`} />
                <p className="text-sm text-slate-600 flex-1">
                  <Link href={`/users/${a.userId}`} className="font-medium text-slate-900 hover:text-indigo-600 transition-colors">
                    {a.userName}
                  </Link>
                  {" "}{a.action}{" "}
                  <Link href={a.itemHref} className="font-medium text-slate-700 hover:text-indigo-600 transition-colors">
                    {a.item}
                  </Link>
                </p>
                <span className="text-[11px] text-slate-400 flex-shrink-0">{timeAgo(a.time)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="space-y-5">
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
            <h2 className="text-sm font-semibold text-slate-800 mb-4">Quick Actions</h2>
            <div className="grid grid-cols-2 gap-2">
              {quickActions.map(a => (
                <Link key={a.href} href={a.href}
                  className={`flex flex-col items-center gap-2 ${a.color} text-white text-xs font-semibold py-4 rounded-xl shadow ${a.shadow} hover:shadow-md transition-all hover:-translate-y-0.5`}>
                  <a.icon className="h-5 w-5" />
                  <span>{a.label}</span>
                </Link>
              ))}
            </div>
          </div>
          {/* Leaderboard mini */}
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-slate-800">Leaderboard</h2>
              <Link href="/leaderboard" className="text-xs text-indigo-600 hover:text-indigo-700 flex items-center gap-1">
                See all <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            <p className="text-xs text-slate-400">Top learners by XP — click to see full leaderboard</p>
          </div>
        </div>
      </div>
    </div>
  )
}

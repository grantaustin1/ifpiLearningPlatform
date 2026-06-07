"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, BookOpen, Award, ClipboardList, Star, Shield, CheckCircle2, XCircle } from "lucide-react"
import { useSession } from "next-auth/react"
import { BADGE_META } from "@/lib/gamification"

interface UserDetail {
  id: string; name: string | null; email?: string; role?: string
  points: number; createdAt?: string; image?: string | null
  badges: { badge: string; earnedAt: string }[]
  enrollments?: Array<{ id: string; status: string; progress: number; enrolledAt: string; completedAt: string | null; course: { id: string; title: string; coverColor: string } }>
  examAttempts?: Array<{ id: string; score: number; passed: boolean; startedAt: string; completedAt: string | null; exam: { id: string; title: string } }>
  certificates?: Array<{ id: string; type: string; code: string; issuedAt: string; course: { title: string } | null; exam: { title: string } | null }>
  _count: { enrollments: number; certificates: number }
}

const ROLE_COLORS: Record<string, string> = {
  ADMIN: "bg-purple-100 text-purple-700",
  SUPER_ADMIN: "bg-red-100 text-red-700",
  INSTRUCTOR: "bg-blue-100 text-blue-700",
  LEARNER: "bg-slate-100 text-slate-600",
}

const ROLES = ["LEARNER", "INSTRUCTOR", "ADMIN"]

export default function UserDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { data: session } = useSession()
  const userId = params.id as string
  const [user, setUser] = useState<UserDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<"overview" | "courses" | "exams" | "certs">("overview")
  const [roleChanging, setRoleChanging] = useState(false)

  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session?.user?.role ?? '')
  const isSelf = session?.user?.id === userId

  useEffect(() => {
    fetch(`/api/users/${userId}`)
      .then(r => r.json())
      .then(d => { setUser(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [userId])

  const changeRole = async (newRole: string) => {
    if (!user) return
    setRoleChanging(true)
    try {
      const res = await fetch(`/api/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: newRole }),
      })
      if (res.ok) setUser({ ...user, role: newRole })
    } finally { setRoleChanging(false) }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  )
  if (!user) return (
    <div className="flex items-center justify-center h-64">
      <p className="text-slate-500">User not found.</p>
    </div>
  )

  const initials = (user.name ?? "?").split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)

  const TABS = [
    { id: "overview" as const, label: "Overview" },
    ...(isAdmin || isSelf ? [
      { id: "courses" as const, label: `Courses (${user.enrollments?.length ?? user._count.enrollments})` },
      { id: "exams" as const, label: `Exams (${user.examAttempts?.length ?? 0})` },
      { id: "certs" as const, label: `Certificates (${user.certificates?.length ?? user._count.certificates})` },
    ] : []),
  ]

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      {/* Back */}
      <div>
        <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
      </div>

      {/* Profile header */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
        <div className="flex items-start gap-5">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold text-xl flex-shrink-0">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-xl font-bold text-slate-900">{user.name ?? "(no name)"}</h1>
              {user.role && (
                <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${ROLE_COLORS[user.role] ?? "bg-slate-100 text-slate-600"}`}>
                  {user.role}
                </span>
              )}
              {isSelf && <span className="text-xs text-indigo-500 font-medium">You</span>}
            </div>
            {user.email && <p className="text-sm text-slate-400 mt-0.5">{user.email}</p>}
            {user.createdAt && (
              <p className="text-xs text-slate-400 mt-1">
                Member since {new Date(user.createdAt).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}
              </p>
            )}
          </div>
          {isAdmin && !isSelf && user.role && (
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-slate-400" />
              <select value={user.role} disabled={roleChanging}
                onChange={e => changeRole(e.target.value)}
                className="text-sm border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-400">
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          )}
        </div>

        {/* Stats strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-5 border-t border-slate-50">
          {[
            { label: "XP Points", value: user.points.toLocaleString(), icon: Star, color: "text-amber-500", bg: "bg-amber-50" },
            { label: "Courses", value: (user.enrollments?.length ?? user._count.enrollments).toString(), icon: BookOpen, color: "text-blue-500", bg: "bg-blue-50" },
            { label: "Certificates", value: (user.certificates?.length ?? user._count.certificates).toString(), icon: Award, color: "text-emerald-500", bg: "bg-emerald-50" },
            { label: "Badges", value: user.badges.length.toString(), icon: ClipboardList, color: "text-violet-500", bg: "bg-violet-50" },
          ].map(s => (
            <div key={s.label} className="flex items-center gap-3">
              <div className={`w-9 h-9 rounded-xl ${s.bg} flex items-center justify-center flex-shrink-0`}>
                <s.icon className={`h-4.5 w-4.5 ${s.color}`} />
              </div>
              <div>
                <p className="text-lg font-bold text-slate-900 leading-none">{s.value}</p>
                <p className="text-[11px] text-slate-400 mt-0.5">{s.label}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-xl w-fit">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === t.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab: Overview (badges) */}
      {activeTab === "overview" && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Badges Earned</h2>
          {user.badges.length === 0 ? (
            <p className="text-sm text-slate-400">No badges earned yet.</p>
          ) : (
            <div className="flex flex-wrap gap-3">
              {user.badges.map(b => {
                const meta = BADGE_META[b.badge]
                return (
                  <div key={b.badge} className="flex items-center gap-2 bg-slate-50 rounded-xl px-3 py-2">
                    <span className="text-2xl">{meta?.emoji ?? "🏅"}</span>
                    <div>
                      <p className="text-xs font-semibold text-slate-800">{meta?.label ?? b.badge}</p>
                      <p className="text-[10px] text-slate-400">{new Date(b.earnedAt).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab: Courses */}
      {activeTab === "courses" && (isAdmin || isSelf) && (
        <div className="space-y-2">
          {!user.enrollments || user.enrollments.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-8">No course enrollments yet.</p>
          ) : user.enrollments.map(e => (
            <Link key={e.id} href={isAdmin ? `/courses/${e.course.id}/edit` : `/learn/${e.course.id}`}
              className="flex items-center gap-4 bg-white rounded-2xl border border-slate-100 shadow-sm px-5 py-4 hover:shadow-md transition-shadow group">
              <div className={`w-10 h-10 rounded-xl ${e.course.coverColor} flex-shrink-0`} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-900 group-hover:text-indigo-600 truncate">{e.course.title}</p>
                <div className="flex items-center gap-3 mt-1.5">
                  <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden max-w-[120px]">
                    <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${e.progress}%` }} />
                  </div>
                  <span className="text-[11px] text-slate-400">{Math.round(e.progress)}%</span>
                </div>
              </div>
              <span className={`text-xs font-medium px-2.5 py-1 rounded-full flex-shrink-0 ${e.status === "COMPLETED" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
                {e.status === "COMPLETED" ? "Completed" : "In Progress"}
              </span>
            </Link>
          ))}
        </div>
      )}

      {/* Tab: Exams */}
      {activeTab === "exams" && (isAdmin || isSelf) && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          {!user.examAttempts || user.examAttempts.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-8">No exam attempts yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-100">
                <tr>
                  <th className="text-left px-5 py-3 font-medium text-slate-500">Exam</th>
                  <th className="text-right px-5 py-3 font-medium text-slate-500">Score</th>
                  <th className="text-right px-5 py-3 font-medium text-slate-500">Result</th>
                  <th className="text-right px-5 py-3 font-medium text-slate-500">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {user.examAttempts.map(a => (
                  <tr key={a.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-3 font-medium text-slate-900">{a.exam.title}</td>
                    <td className="px-5 py-3 text-right">{a.completedAt ? `${Math.round(a.score)}%` : "—"}</td>
                    <td className="px-5 py-3 text-right">
                      {a.completedAt ? (
                        a.passed
                          ? <span className="inline-flex items-center gap-1 text-emerald-600"><CheckCircle2 className="h-3.5 w-3.5" /> Passed</span>
                          : <span className="inline-flex items-center gap-1 text-red-500"><XCircle className="h-3.5 w-3.5" /> Failed</span>
                      ) : <span className="text-slate-400">In progress</span>}
                    </td>
                    <td className="px-5 py-3 text-right text-slate-400 text-xs">
                      {new Date(a.startedAt).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab: Certificates */}
      {activeTab === "certs" && (isAdmin || isSelf) && (
        <div className="space-y-2">
          {!user.certificates || user.certificates.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-8">No certificates issued yet.</p>
          ) : user.certificates.map(c => (
            <div key={c.id} className="flex items-center gap-4 bg-white rounded-2xl border border-slate-100 shadow-sm px-5 py-4">
              <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center flex-shrink-0">
                <Award className="h-5 w-5 text-amber-500" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-900 truncate">
                  {c.course?.title ?? c.exam?.title ?? "Certificate"}
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5 font-mono">#{c.code.slice(0, 12)}…</p>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-xs text-slate-400">{new Date(c.issuedAt).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}</p>
                <span className="text-[10px] font-medium text-amber-600 uppercase">{c.type}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

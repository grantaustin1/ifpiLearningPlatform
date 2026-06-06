"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard, BookOpen, ClipboardList, Award, BarChart3,
  Users, Settings, GraduationCap, LogOut, Building2, Route,
  Trophy, FileText, Video, Globe,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { signOut, useSession } from "next-auth/react"

const adminNavItems = [
  { href: "/dashboard",      label: "Dashboard",      icon: LayoutDashboard },
  { href: "/courses",        label: "Courses",         icon: BookOpen },
  { href: "/exams",          label: "Exams",           icon: ClipboardList },
  { href: "/learning-paths", label: "Learning Paths",  icon: Route },
  { href: "/certificates",   label: "Certificates",    icon: Award },
  { href: "/leaderboard",    label: "Leaderboard",     icon: Trophy },
  { href: "/assignments",    label: "Grading Queue",   icon: FileText },
  { href: "/live-sessions",  label: "Live Sessions",   icon: Video },
  { href: "/reports",        label: "Reports",         icon: BarChart3 },
  { href: "/users",          label: "Users",           icon: Users },
  { href: "/academies",      label: "Academies",       icon: Building2 },
  { href: "/catalog",        label: "Public Catalog",  icon: Globe },
  { href: "/settings",       label: "Settings",        icon: Settings },
]

const learnerNavItems = [
  { href: "/courses",        label: "My Courses",      icon: BookOpen },
  { href: "/learning-paths", label: "Learning Paths",  icon: Route },
  { href: "/certificates",   label: "My Certificates", icon: Award },
  { href: "/leaderboard",    label: "Leaderboard",     icon: Trophy },
  { href: "/live-sessions",  label: "Live Sessions",   icon: Video },
]

export function Sidebar() {
  const pathname = usePathname()
  const { data: session } = useSession()

  const isAdmin = session?.user?.role === "ADMIN" || session?.user?.role === "SUPER_ADMIN" || session?.user?.role === "INSTRUCTOR"
  const navItems = isAdmin ? adminNavItems : learnerNavItems
  const portalLabel = isAdmin ? "Admin Portal" : "Learner Portal"
  const homeHref = isAdmin ? "/dashboard" : "/courses"

  const userInitials = session?.user?.name
    ? session.user.name.split(" ").map((n: string) => n[0]).join("").toUpperCase().slice(0, 2) : "?"
  const userRole = session?.user?.role === "ADMIN" || session?.user?.role === "SUPER_ADMIN" ? "Administrator" : session?.user?.role === "INSTRUCTOR" ? "Instructor" : "Learner"

  return (
    <div className="w-60 flex flex-col h-screen bg-[#0f172a] border-r border-white/5">
      <div className="px-5 py-5 border-b border-white/5">
        <Link href={homeHref} className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <GraduationCap className="text-white" style={{ width: 18, height: 18 }} />
          </div>
          <div>
            <span className="text-white font-semibold text-sm tracking-tight">IFPI Learning</span>
            <p className="text-[10px] text-slate-500 leading-none mt-0.5">{portalLabel}</p>
          </div>
        </Link>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {navItems.map(item => {
          const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"))
          return (
            <Link key={item.href} href={item.href}
              className={cn("flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-150 group",
                isActive ? "bg-indigo-500/10 text-indigo-300" : "text-slate-400 hover:text-slate-200 hover:bg-white/5")}>
              <item.icon style={{ width: 16, height: 16 }}
                className={cn("flex-shrink-0 transition-colors", isActive ? "text-indigo-400" : "text-slate-500 group-hover:text-slate-300")} />
              <span className="truncate">{item.label}</span>
            </Link>
          )
        })}
      </nav>

      <div className="px-3 pb-4 border-t border-white/5 pt-3 space-y-1">
        <Link href="/profile"
          className={cn("flex items-center gap-2.5 px-3 py-2 rounded-lg transition-all group", pathname === "/profile" ? "bg-indigo-500/10" : "hover:bg-white/5")}>
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center flex-shrink-0">
            <span className="text-[10px] font-bold text-white">{userInitials}</span>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-300 leading-none truncate group-hover:text-slate-100">{session?.user?.name ?? "…"}</p>
            <p className="text-[10px] text-slate-500 mt-0.5">{userRole}</p>
          </div>
        </Link>
        <button onClick={() => signOut({ redirectTo: "/login" })}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium text-slate-500 hover:text-slate-200 hover:bg-white/5 transition-all">
          <LogOut style={{ width: 16, height: 16 }} className="text-slate-600 flex-shrink-0" />
          Sign out
        </button>
      </div>
    </div>
  )
}

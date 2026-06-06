"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard, BookOpen, ClipboardList, Award,
  BarChart3, Users, Settings, GraduationCap, LogOut,
  Building2, Route, ChevronRight,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { signOut } from "next-auth/react"

const navItems = [
  { href: "/dashboard",      label: "Dashboard",      icon: LayoutDashboard },
  { href: "/courses",        label: "Courses",         icon: BookOpen },
  { href: "/exams",          label: "Exams",           icon: ClipboardList },
  { href: "/learning-paths", label: "Learning Paths",  icon: Route },
  { href: "/certificates",   label: "Certificates",    icon: Award },
  { href: "/reports",        label: "Reports",         icon: BarChart3 },
  { href: "/users",          label: "Users",           icon: Users },
  { href: "/academies",      label: "Academies",       icon: Building2 },
  { href: "/settings",       label: "Settings",        icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <div className="w-60 flex flex-col h-screen bg-[#0f172a] border-r border-white/5">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-white/5">
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <GraduationCap className="h-4.5 w-4.5 text-white" style={{ width: 18, height: 18 }} />
          </div>
          <div>
            <span className="text-white font-semibold text-sm tracking-tight">IFPI Learning</span>
            <p className="text-[10px] text-slate-500 leading-none mt-0.5">Admin Portal</p>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {navItems.map(item => {
          const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"))
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-150 group",
                isActive
                  ? "bg-indigo-500/10 text-indigo-300 sidebar-active"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
              )}
            >
              <item.icon
                style={{ width: 16, height: 16 }}
                className={cn(
                  "flex-shrink-0 transition-colors",
                  isActive ? "text-indigo-400" : "text-slate-500 group-hover:text-slate-300"
                )}
              />
              <span className="truncate">{item.label}</span>
              {isActive && (
                <ChevronRight style={{ width: 12, height: 12 }} className="ml-auto text-indigo-500/60" />
              )}
            </Link>
          )
        })}
      </nav>

      {/* Divider label */}
      <div className="px-5 pb-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-600">Account</p>
      </div>

      {/* Sign out */}
      <div className="px-3 pb-4">
        <button
          onClick={() => signOut({ callbackUrl: "/login" })}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium text-slate-500 hover:text-slate-200 hover:bg-white/5 transition-all"
        >
          <LogOut style={{ width: 16, height: 16 }} className="text-slate-600 flex-shrink-0" />
          Sign out
        </button>
      </div>
    </div>
  )
}

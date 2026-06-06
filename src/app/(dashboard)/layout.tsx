import { auth } from "@/lib/auth"
import { redirect } from "next/navigation"
import { Sidebar } from "@/components/layout/sidebar"
import { Bell, Search } from "lucide-react"

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const session = await auth()
  if (!session) redirect('/login')

  const initials = session.user.name
    ? session.user.name
        .split(' ')
        .map((n: string) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : '?'

  const roleLabel =
    session.user.role === 'ADMIN'
      ? 'Administrator'
      : session.user.role === 'INSTRUCTOR'
      ? 'Instructor'
      : 'Learner'

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Topbar */}
        <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 flex-shrink-0">
          <div className="flex items-center gap-2.5 w-72">
            <Search className="h-4 w-4 text-slate-400 flex-shrink-0" />
            <input
              placeholder="Search courses, users..."
              className="text-sm text-slate-600 placeholder:text-slate-400 bg-transparent outline-none w-full"
            />
          </div>
          <div className="flex items-center gap-3">
            <button className="relative w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:bg-slate-100 transition-colors">
              <Bell className="h-4 w-4" />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-indigo-500 rounded-full" />
            </button>
            <div className="flex items-center gap-2.5 pl-3 border-l border-slate-200">
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
                <span className="text-[10px] font-bold text-white">{initials}</span>
              </div>
              <div className="hidden sm:block">
                <p className="text-xs font-semibold text-slate-700 leading-none">
                  {session.user.name}
                </p>
                <p className="text-[10px] text-slate-400 mt-0.5">{roleLabel}</p>
              </div>
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}

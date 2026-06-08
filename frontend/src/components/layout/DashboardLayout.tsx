import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from 'contexts/AuthContext'
import {
  LayoutDashboard, BookOpen, ClipboardList, Award, BarChart3, Users,
  GraduationCap, LogOut, Trophy, CreditCard, Globe, Layers, Mail, Settings, Building2,
} from 'lucide-react'
import { cn } from 'lib/utils'

const ADMIN_NAV = [
  { href: '/dashboard',     label: 'Dashboard',    icon: LayoutDashboard },
  { href: '/courses',       label: 'Courses',      icon: BookOpen },
  { href: '/learning-paths',label: 'Learning Paths', icon: Layers },
  { href: '/exams',         label: 'Exams',        icon: ClipboardList },
  { href: '/certificates',  label: 'Certificates', icon: Award },
  { href: '/leaderboard',   label: 'Leaderboard',  icon: Trophy },
  { href: '/badge-tiers',   label: 'Badge tiers',  icon: Award },
  { href: '/reports',       label: 'Reports',      icon: BarChart3 },
  { href: '/users',         label: 'Users',        icon: Users },
  { href: '/outbox',        label: 'Email Outbox', icon: Mail },
  { href: '/billing',       label: 'Billing',      icon: CreditCard },
  { href: '/settings',      label: 'Settings',     icon: Settings },
  { href: '/academies',     label: 'Academies',    icon: Building2 },
  { href: '/catalog',       label: 'Public Catalog', icon: Globe },
]

const LEARNER_NAV = [
  { href: '/courses',       label: 'My Courses',     icon: BookOpen },
  { href: '/learning-paths',label: 'Learning Paths', icon: Layers },
  { href: '/certificates',  label: 'My Certificates',icon: Award },
  { href: '/leaderboard',   label: 'Leaderboard',    icon: Trophy },
  { href: '/billing',       label: 'Subscriptions',  icon: CreditCard },
]

export default function DashboardLayout() {
  const { user, logout, hasRole } = useAuth()
  const nav = useNavigate()
  const isAdmin = hasRole('ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR')
  const items = isAdmin ? ADMIN_NAV : LEARNER_NAV
  const initials = (user?.name || '?').split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)

  const handleLogout = async () => { await logout(); nav('/login') }

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-60 flex-shrink-0 bg-ink-900 text-slate-300 flex flex-col">
        <div className="px-5 py-5 border-b border-white/5">
          <Link to={isAdmin ? '/dashboard' : '/courses'} className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <GraduationCap className="text-white h-4 w-4" />
            </div>
            <div>
              <p className="text-white font-semibold text-sm">IFPI Learning</p>
              <p className="text-[10px] text-slate-500 mt-0.5">{isAdmin ? 'Admin Portal' : 'Learner Portal'}</p>
            </div>
          </Link>
        </div>
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto" data-testid="sidebar-nav">
          {items.map(item => (
            <NavLink key={item.href} to={item.href} end
              data-testid={`nav-${item.href.replace('/', '')}`}
              className={({ isActive }) => cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all',
                isActive ? 'bg-indigo-500/15 text-indigo-300'
                         : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              )}>
              <item.icon className="h-4 w-4 flex-shrink-0" />
              <span className="truncate">{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-white/5 p-3">
          <div className="flex items-center gap-2.5 px-2 py-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <span className="text-[10px] font-bold text-white">{initials}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-200 truncate">{user?.name}</p>
              <p className="text-[10px] text-slate-500">{user?.roles?.[0] || 'LEARNER'}</p>
            </div>
          </div>
          <button onClick={handleLogout} data-testid="logout-btn"
            className="w-full flex items-center gap-3 px-3 py-2 mt-1 rounded-lg text-[13px] font-medium text-slate-500 hover:text-slate-200 hover:bg-white/5 transition-all">
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto bg-slate-50">
        <Outlet />
      </main>
    </div>
  )
}

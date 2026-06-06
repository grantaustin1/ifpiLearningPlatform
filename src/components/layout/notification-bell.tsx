"use client"

import { useState, useEffect, useRef } from "react"
import { Bell, CheckCheck, X } from "lucide-react"
import Link from "next/link"
import { cn } from "@/lib/utils"

interface Notification {
  id: string; type: string; title: string; message: string
  isRead: boolean; link?: string; createdAt: string
}

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (seconds < 60) return "just now"
  const mins = Math.floor(seconds / 60)
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const fetchNotifications = async () => {
    try {
      const res = await fetch("/api/notifications")
      if (!res.ok) return
      const data = await res.json()
      setNotifications(data.notifications ?? [])
      setUnreadCount(data.unreadCount ?? 0)
    } catch {}
  }

  useEffect(() => {
    fetchNotifications()
    const interval = setInterval(fetchNotifications, 30_000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const markAllRead = async () => {
    await fetch("/api/notifications", { method: "PATCH" })
    setNotifications(n => n.map(x => ({ ...x, isRead: true })))
    setUnreadCount(0)
  }

  const markRead = async (id: string) => {
    await fetch(`/api/notifications/${id}`, { method: "PATCH" })
    setNotifications(n => n.map(x => x.id === id ? { ...x, isRead: true } : x))
    setUnreadCount(c => Math.max(0, c - 1))
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="relative w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:bg-slate-100 transition-colors"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 bg-indigo-500 rounded-full text-[9px] font-bold text-white flex items-center justify-center px-0.5">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-10 w-80 bg-white rounded-xl shadow-lg border border-slate-200 z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-800">Notifications</h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button onClick={markAllRead} className="text-[11px] text-indigo-600 hover:text-indigo-700 flex items-center gap-1">
                  <CheckCheck className="h-3 w-3" /> Mark all read
                </button>
              )}
              <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <div className="max-h-80 overflow-y-auto divide-y divide-slate-50">
            {notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-slate-400">No notifications yet</div>
            ) : (
              notifications.map(n => (
                <div
                  key={n.id}
                  className={cn("px-4 py-3 hover:bg-slate-50 transition-colors cursor-pointer", !n.isRead && "bg-indigo-50/60")}
                  onClick={() => { if (!n.isRead) markRead(n.id) }}
                >
                  {n.link ? (
                    <Link href={n.link} onClick={() => setOpen(false)}>
                      <NotifItem n={n} />
                    </Link>
                  ) : <NotifItem n={n} />}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function NotifItem({ n }: { n: Notification }) {
  return (
    <div className="flex items-start gap-2.5">
      {!n.isRead && <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full mt-1.5 flex-shrink-0" />}
      <div className={cn("min-w-0", n.isRead && "pl-4")}>
        <p className="text-xs font-semibold text-slate-800 leading-tight">{n.title}</p>
        <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{n.message}</p>
        <p className="text-[10px] text-slate-400 mt-1">{timeAgo(n.createdAt)}</p>
      </div>
    </div>
  )
}

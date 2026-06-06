"use client"

import { useState, useEffect } from "react"
import { useSession } from "next-auth/react"
import { User, Lock, CheckCircle2, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"

const ROLE_META: Record<string, { label: string; color: string }> = {
  ADMIN:      { label: "Administrator", color: "bg-indigo-100 text-indigo-700" },
  INSTRUCTOR: { label: "Instructor",    color: "bg-violet-100 text-violet-700" },
  LEARNER:    { label: "Learner",        color: "bg-slate-100  text-slate-600"  },
}

export default function ProfilePage() {
  const { data: session, update } = useSession()
  const [name, setName]         = useState("")
  const [currentPw, setCurrentPw] = useState("")
  const [newPw, setNewPw]         = useState("")
  const [confirmPw, setConfirmPw] = useState("")
  const [nameState, setNameState] = useState<"idle" | "saving" | "success" | "error">("idle")
  const [pwState,   setPwState]   = useState<"idle" | "saving" | "success" | "error">("idle")
  const [pwError,   setPwError]   = useState("")

  // Initialise name once session loads
  useEffect(() => {
    if (session?.user?.name) setName(session.user.name)
  }, [session?.user?.name])

  const initials = name
    ? name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2)
    : "?"

  const role     = session?.user?.role ?? "LEARNER"
  const roleMeta = ROLE_META[role] ?? ROLE_META.LEARNER

  async function saveName(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setNameState("saving")
    try {
      const res = await fetch("/api/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      })
      if (!res.ok) throw new Error()
      await update({ name: name.trim() })
      setNameState("success")
      setTimeout(() => setNameState("idle"), 3000)
    } catch {
      setNameState("error")
      setTimeout(() => setNameState("idle"), 3000)
    }
  }

  async function changePassword(e: React.FormEvent) {
    e.preventDefault()
    setPwError("")
    if (newPw !== confirmPw) { setPwError("New passwords don't match"); return }
    if (newPw.length < 8)    { setPwError("New password must be at least 8 characters"); return }
    setPwState("saving")
    try {
      const res  = await fetch("/api/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ currentPassword: currentPw, newPassword: newPw }),
      })
      const data = await res.json()
      if (!res.ok) {
        setPwError(data.error ?? "Failed to update password")
        setPwState("error")
        setTimeout(() => setPwState("idle"), 3000)
        return
      }
      setPwState("success")
      setCurrentPw(""); setNewPw(""); setConfirmPw("")
      setTimeout(() => setPwState("idle"), 3000)
    } catch {
      setPwError("Something went wrong")
      setPwState("error")
      setTimeout(() => setPwState("idle"), 3000)
    }
  }

  const inputCls =
    "w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-400 transition-all"
  const btnCls =
    "flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-sm font-semibold rounded-xl shadow-sm shadow-indigo-200 transition-all"

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-slate-900">Account Settings</h1>
        <p className="text-sm text-slate-500 mt-1">Manage your profile and password</p>
      </div>

      {/* ── Profile info card ─────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 mb-5">
        {/* Avatar + summary */}
        <div className="flex items-center gap-4 mb-6 pb-6 border-b border-slate-100">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-200 flex-shrink-0">
            <span className="text-base font-bold text-white">{initials}</span>
          </div>
          <div>
            <p className="text-base font-semibold text-slate-900">{name || "\u2014"}</p>
            <p className="text-sm text-slate-500">{session?.user?.email}</p>
            <span className={cn("inline-block mt-1.5 text-xs font-semibold px-2.5 py-0.5 rounded-full", roleMeta.color)}>
              {roleMeta.label}
            </span>
          </div>
        </div>

        <form onSubmit={saveName} className="space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <User className="h-4 w-4 text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-700">Profile Info</h2>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">
                Full name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={inputCls}
                placeholder="Your full name"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">
                Email address
              </label>
              <input
                value={session?.user?.email ?? ""}
                disabled
                className="w-full px-4 py-2.5 bg-slate-100 border border-slate-200 rounded-xl text-sm text-slate-400 cursor-not-allowed"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <span className="text-xs">
              {nameState === "success" && (
                <span className="flex items-center gap-1.5 text-emerald-600 font-medium">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Saved
                </span>
              )}
              {nameState === "error" && (
                <span className="flex items-center gap-1.5 text-red-500 font-medium">
                  <AlertCircle className="h-3.5 w-3.5" /> Failed to save
                </span>
              )}
            </span>
            <button type="submit" disabled={nameState === "saving"} className={btnCls}>
              {nameState === "saving" && (
                <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              )}
              Save changes
            </button>
          </div>
        </form>
      </div>

      {/* ── Change password card ───────────────────────────── */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
        <form onSubmit={changePassword} className="space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <Lock className="h-4 w-4 text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-700">Change Password</h2>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">
              Current password
            </label>
            <input
              type="password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              className={inputCls}
              placeholder="\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"
              required
              autoComplete="current-password"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">
                New password
              </label>
              <input
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                className={inputCls}
                placeholder="Min. 8 characters"
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">
                Confirm new password
              </label>
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                className={inputCls}
                placeholder="Repeat new password"
                required
                autoComplete="new-password"
              />
            </div>
          </div>

          {pwError && (
            <p className="flex items-center gap-1.5 text-xs text-red-500 font-medium">
              <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" /> {pwError}
            </p>
          )}

          <div className="flex items-center justify-between pt-2">
            <span className="text-xs">
              {pwState === "success" && (
                <span className="flex items-center gap-1.5 text-emerald-600 font-medium">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Password updated
                </span>
              )}
            </span>
            <button type="submit" disabled={pwState === "saving"} className={btnCls}>
              {pwState === "saving" && (
                <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              )}
              Update password
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

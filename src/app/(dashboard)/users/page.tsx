"use client"

import { useState, useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import {
  Plus, Search, Upload, CheckCircle, XCircle,
  Shield, BookOpen, Award, MoreVertical, Loader2, X,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface User {
  id: string; name: string | null; email: string; role: string
  points: number; enrollments: number; completed: number; certificates: number
  createdAt: string
}

const roleColors: Record<string, string> = {
  ADMIN:      "bg-purple-100 text-purple-700",
  INSTRUCTOR: "bg-blue-100 text-blue-700",
  LEARNER:    "bg-slate-100 text-slate-600",
}

function ImportResult({ result, onClose }: {
  result: { imported: number; skipped: number; errors: string[] }
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-base font-semibold text-slate-900">Import Results</h2>
          <button onClick={onClose}><X className="h-4 w-4 text-slate-400" /></button>
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-emerald-50 rounded-xl p-4 text-center">
              <CheckCircle className="h-6 w-6 text-emerald-500 mx-auto mb-1" />
              <p className="text-2xl font-bold text-emerald-700">{result.imported}</p>
              <p className="text-xs text-emerald-600">Imported</p>
            </div>
            <div className="bg-amber-50 rounded-xl p-4 text-center">
              <XCircle className="h-6 w-6 text-amber-400 mx-auto mb-1" />
              <p className="text-2xl font-bold text-amber-700">{result.skipped}</p>
              <p className="text-xs text-amber-600">Skipped (existing)</p>
            </div>
          </div>
          {result.errors.length > 0 && (
            <div className="bg-red-50 border border-red-100 rounded-xl p-3 max-h-40 overflow-y-auto">
              <p className="text-xs font-semibold text-red-700 mb-2">Errors ({result.errors.length})</p>
              <ul className="space-y-1">
                {result.errors.map((e, i) => (
                  <li key={i} className="text-[11px] text-red-600">{e}</li>
                ))}
              </ul>
            </div>
          )}
          <Button className="w-full bg-indigo-600 hover:bg-indigo-700" onClick={onClose}>Done</Button>
        </div>
      </div>
    </div>
  )
}

function ImportModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: (r: { imported: number; skipped: number; errors: string[] }) => void }) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = (f: File) => {
    if (!f.name.endsWith(".csv")) { setError("Please upload a .csv file"); return }
    setFile(f); setError("")
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handleSubmit = async () => {
    if (!file) return
    setUploading(true); setError("")
    try {
      const fd = new FormData()
      fd.append("file", file)
      const res = await fetch("/api/admin/users/import", { method: "POST", body: fd })
      const data = await res.json()
      if (!res.ok) { setError(data.error ?? "Import failed"); setUploading(false); return }
      onSuccess(data)
    } catch {
      setError("Network error. Try again.")
      setUploading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-base font-semibold text-slate-900">Import Users from CSV</h2>
          <button onClick={onClose}><X className="h-4 w-4 text-slate-400" /></button>
        </div>
        <div className="p-6 space-y-4">
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-[11px] text-slate-600">
            <p className="font-semibold text-slate-700 mb-1">CSV Format</p>
            <code className="block font-mono">name,email,password,role</code>
            <code className="block font-mono text-slate-400">Jane Smith,jane@example.com,pass123,LEARNER</code>
            <p className="mt-1.5 text-slate-500">Roles: LEARNER (default), INSTRUCTOR, ADMIN — Minimum password: 6 chars</p>
          </div>

          <div
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${dragging ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:border-indigo-300 hover:bg-slate-50"}`}
          >
            <Upload className="h-8 w-8 text-slate-300 mx-auto mb-2" />
            {file ? (
              <div>
                <p className="text-sm font-semibold text-slate-800">{file.name}</p>
                <p className="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
            ) : (
              <div>
                <p className="text-sm font-semibold text-slate-700">Drop your CSV here</p>
                <p className="text-xs text-slate-400 mt-0.5">or click to browse</p>
              </div>
            )}
            <input ref={inputRef} type="file" accept=".csv" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />
          </div>

          {error && <p className="text-xs text-red-600">{error}</p>}

          <div className="flex gap-3">
            <Button variant="outline" className="flex-1" onClick={onClose}>Cancel</Button>
            <Button
              className="flex-1 bg-indigo-600 hover:bg-indigo-700"
              disabled={!file || uploading}
              onClick={handleSubmit}
            >
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Import"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [roleFilter, setRoleFilter] = useState("ALL")
  const router = useRouter()
  const [showImport, setShowImport] = useState(false)
  const [importResult, setImportResult] = useState<{ imported: number; skipped: number; errors: string[] } | null>(null)

  const loadUsers = async () => {
    try {
      const res = await fetch("/api/admin/users")
      if (res.ok) setUsers(await res.json())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadUsers() }, [])

  const filtered = users.filter(u => {
    const matchRole = roleFilter === "ALL" || u.role === roleFilter
    const q = search.toLowerCase()
    const matchSearch = !q || (u.name ?? "").toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
    return matchRole && matchSearch
  })

  const learners = users.filter(u => u.role === "LEARNER").length
  const certs = users.reduce((a, u) => a + u.certificates, 0)

  const handleImportSuccess = (result: { imported: number; skipped: number; errors: string[] }) => {
    setShowImport(false)
    setImportResult(result)
    loadUsers() // refresh list
  }

  return (
    <div className="p-6 lg:p-8 max-w-7xl">
      {showImport && (
        <ImportModal onClose={() => setShowImport(false)} onSuccess={handleImportSuccess} />
      )}
      {importResult && (
        <ImportResult result={importResult} onClose={() => setImportResult(null)} />
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Users</h1>
          <p className="text-sm text-slate-500 mt-0.5">{loading ? "Loading…" : `${users.length} members total`}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="gap-2 text-sm" onClick={() => setShowImport(true)}>
            <Upload className="h-4 w-4" /> Import CSV
          </Button>
          <Button className="bg-indigo-600 hover:bg-indigo-700 gap-2 text-sm">
            <Plus className="h-4 w-4" /> Invite User
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: "Total Users",       value: users.length,  icon: Shield,   color: "text-indigo-600", bg: "bg-indigo-50" },
          { label: "Active Learners",   value: learners,      icon: BookOpen, color: "text-emerald-600", bg: "bg-emerald-50" },
          { label: "Certificates Earned", value: certs,       icon: Award,    color: "text-amber-600",  bg: "bg-amber-50" },
        ].map(s => (
          <Card key={s.label} className="border-0 shadow-sm">
            <CardContent className="p-5 flex items-center gap-4">
              <div className={`p-2.5 rounded-xl ${s.bg}`}>
                <s.icon className={`h-5 w-5 ${s.color}`} />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900 leading-none">{s.value}</p>
                <p className="text-xs text-slate-500 mt-1">{s.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
            placeholder="Search name or email..."
          />
        </div>
        <select
          value={roleFilter}
          onChange={e => setRoleFilter(e.target.value)}
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
        >
          <option value="ALL">All roles</option>
          <option value="ADMIN">Admin</option>
          <option value="INSTRUCTOR">Instructor</option>
          <option value="LEARNER">Learner</option>
        </select>
      </div>

      {/* Table */}
      <Card className="border-0 shadow-sm overflow-hidden">
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-7 h-7 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-16 text-center text-sm text-slate-400">No users match your search</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-100">
                <tr>
                  <th className="text-left px-6 py-3 font-medium text-slate-500">User</th>
                  <th className="text-left px-6 py-3 font-medium text-slate-500">Role</th>
                  <th className="text-right px-6 py-3 font-medium text-slate-500">XP</th>
                  <th className="text-right px-6 py-3 font-medium text-slate-500">Enrolled</th>
                  <th className="text-right px-6 py-3 font-medium text-slate-500">Completed</th>
                  <th className="text-right px-6 py-3 font-medium text-slate-500">Certs</th>
                  <th className="text-right px-6 py-3 font-medium text-slate-500">Joined</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {filtered.map(u => {
                  const initials = (u.name ?? "?").split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)
                  const joined = new Date(u.createdAt).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })
                  return (
                    <tr key={u.id} onClick={() => router.push(`/users/${u.id}`)} className="hover:bg-slate-50 transition-colors cursor-pointer">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold text-xs flex-shrink-0">
                            {initials}
                          </div>
                          <div>
                            <p className="font-medium text-slate-900">{u.name ?? "(no name)"}</p>
                            <p className="text-xs text-slate-400">{u.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${roleColors[u.role] ?? "bg-slate-100"}`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right text-slate-600 font-medium">{u.points.toLocaleString()}</td>
                      <td className="px-6 py-4 text-right text-slate-600">{u.enrollments}</td>
                      <td className="px-6 py-4 text-right text-slate-600">{u.completed}</td>
                      <td className="px-6 py-4 text-right text-slate-600">{u.certificates}</td>
                      <td className="px-6 py-4 text-right text-slate-400 text-xs">{joined}</td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-slate-300 text-xs">→</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

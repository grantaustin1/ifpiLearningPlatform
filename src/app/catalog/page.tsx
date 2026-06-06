"use client"

import { useState, useEffect } from "react"
import { BookOpen, Clock, Users, Search, ArrowRight, GraduationCap } from "lucide-react"
import Link from "next/link"

interface CatalogCourse {
  id: string; title: string; description: string | null; category: string | null
  coverColor: string; duration: number | null; createdAt: string
  _count: { slides: number; enrollments: number }
}

export default function CatalogPage() {
  const [courses, setCourses] = useState<CatalogCourse[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState("")
  const [selectedCategory, setSelectedCategory] = useState("")

  const load = async (query = q, cat = selectedCategory) => {
    const params = new URLSearchParams()
    if (query) params.set("q", query)
    if (cat) params.set("category", cat)
    try {
      const res = await fetch(`/api/catalog?${params}`)
      if (res.ok) {
        const data = await res.json()
        setCourses(data.courses ?? [])
        setCategories(data.categories ?? [])
      }
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    load()
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50">
      {/* Hero */}
      <div className="bg-gradient-to-br from-[#0f172a] via-indigo-950 to-[#0f172a] text-white">
        <div className="max-w-6xl mx-auto px-6 py-16">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg">
              <GraduationCap className="h-5 w-5 text-white" />
            </div>
            <span className="font-semibold text-indigo-300 text-sm">IFPI Learning Platform</span>
          </div>
          <h1 className="text-4xl font-bold mb-4 tracking-tight">Course Catalog</h1>
          <p className="text-slate-400 text-lg max-w-xl">Explore all available courses. Sign in to enrol and track your progress.</p>
          <form onSubmit={handleSearch} className="mt-8 flex gap-3 max-w-lg">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input value={q} onChange={e => setQ(e.target.value)}
                placeholder="Search courses..."
                className="w-full pl-10 pr-4 py-2.5 bg-white/10 border border-white/20 rounded-xl text-white placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent" />
            </div>
            <button type="submit"
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-sm font-medium transition-colors">
              Search
            </button>
          </form>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-6 py-10">
        {/* Category filters */}
        {categories.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-8">
            <button onClick={() => { setSelectedCategory(""); load(q, "") }}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${selectedCategory === "" ? "bg-indigo-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:text-indigo-600"}`}>
              All
            </button>
            {categories.map(cat => (
              <button key={cat} onClick={() => { setSelectedCategory(cat ?? ""); load(q, cat ?? "") }}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${selectedCategory === cat ? "bg-indigo-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:text-indigo-600"}`}>
                {cat}
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : courses.length === 0 ? (
          <div className="text-center py-20">
            <BookOpen className="h-12 w-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500 text-lg">No courses found</p>
            {(q || selectedCategory) && (
              <button onClick={() => { setQ(""); setSelectedCategory(""); load("", "") }}
                className="mt-3 text-sm text-indigo-600 hover:underline">Clear filters</button>
            )}
          </div>
        ) : (
          <>
            <p className="text-sm text-slate-500 mb-6">{courses.length} course{courses.length !== 1 ? "s" : ""} available</p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {courses.map(c => (
                <div key={c.id} className="bg-white rounded-2xl overflow-hidden shadow-sm border border-slate-100 hover:shadow-md transition-all hover:-translate-y-0.5 flex flex-col">
                  <div className={`h-36 ${c.coverColor} flex items-end p-4`}>
                    {c.category && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-white/20 text-white">{c.category}</span>
                    )}
                  </div>
                  <div className="p-5 flex-1 flex flex-col">
                    <h2 className="font-semibold text-slate-900 text-sm leading-tight line-clamp-2">{c.title}</h2>
                    {c.description && (
                      <p className="text-xs text-slate-500 mt-1.5 line-clamp-2 leading-relaxed">{c.description}</p>
                    )}
                    <div className="flex items-center gap-4 mt-3 text-xs text-slate-400">
                      <span className="flex items-center gap-1"><BookOpen className="h-3.5 w-3.5" /> {c._count.slides} slides</span>
                      <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {c._count.enrollments} enrolled</span>
                      {c.duration && <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {c.duration}m</span>}
                    </div>
                    <div className="mt-auto pt-4">
                      <Link href={`/login?redirect=/learn/${c.id}`}
                        className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors">
                        Enrol Now <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <footer className="mt-16 border-t border-slate-200 bg-white py-8">
        <div className="max-w-6xl mx-auto px-6 text-center text-sm text-slate-400">
          <p>© {new Date().getFullYear()} IFPI Learning Platform. All rights reserved.</p>
          <p className="mt-1"><Link href="/login" className="text-indigo-600 hover:underline">Sign in</Link> to access your courses.</p>
        </div>
      </footer>
    </div>
  )
}

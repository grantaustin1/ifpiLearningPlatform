/**
 * DocsEngagementTile — Iter 33c.
 *
 * Reads /api/admin/dashboard/docs-engagement and surfaces whether admins
 * are actually reading the setup / user manuals. Idea: turn the
 * Documents tab into a real onboarding signal instead of a dead shelf.
 *
 * Placed on the Owner dashboard next to "Quick Actions".
 */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from 'lib/api'
import { BookOpen, ArrowRight, FileText } from 'lucide-react'

type Engagement = {
  window_days: number
  total_events: number
  unique_docs: number
  unique_readers: number
  top_docs: { slug: string; title: string; count: number }[]
  latest_at: string | null
}

export function DocsEngagementTile() {
  const { data, isLoading } = useQuery<Engagement>({
    queryKey: ['docs-engagement'],
    queryFn: async () => (await api.get('/admin/dashboard/docs-engagement?days=7')).data,
    staleTime: 5 * 60 * 1000, // 5 min
  })

  if (isLoading) {
    return (
      <div
        className="bg-white rounded-2xl card-glow p-5 min-h-[220px] flex items-center justify-center"
        data-testid="docs-engagement-loading"
      >
        <div className="w-6 h-6 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const total = data?.total_events ?? 0
  const topDocs = data?.top_docs ?? []

  return (
    <div className="bg-white rounded-2xl card-glow p-5" data-testid="docs-engagement-tile">
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <BookOpen className="h-4 w-4 text-indigo-500" />
            <h2 className="text-sm font-semibold text-slate-800">Docs opened this week</h2>
          </div>
          <p className="text-xs text-slate-500">Setup + User manual engagement (last 7 days)</p>
        </div>
        <Link
          to="/settings"
          data-testid="docs-engagement-open-library"
          className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 inline-flex items-center gap-1"
        >
          Open library <ArrowRight className="h-3 w-3" />
        </Link>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-4">
        <StatBox label="Total opens" value={total} testid="docs-engagement-total" />
        <StatBox label="Unique docs" value={data?.unique_docs ?? 0} testid="docs-engagement-docs" />
        <StatBox label="Unique admins" value={data?.unique_readers ?? 0} testid="docs-engagement-readers" />
      </div>

      {total === 0 ? (
        <div
          className="text-center py-6 text-xs text-slate-400 border border-dashed border-slate-200 rounded-lg"
          data-testid="docs-engagement-empty"
        >
          No manuals opened yet this week.<br />
          <Link to="/settings" className="text-indigo-600 hover:text-indigo-800 font-medium">
            Preview one now →
          </Link>
        </div>
      ) : (
        <ul className="space-y-2" data-testid="docs-engagement-top-list">
          {topDocs.map((d) => (
            <li
              key={d.slug}
              data-testid={`docs-engagement-doc-${d.slug}`}
              className="flex items-center gap-3 text-xs"
            >
              <FileText className="h-3.5 w-3.5 text-indigo-500 flex-shrink-0" />
              <span className="text-slate-700 flex-1 truncate">{d.title}</span>
              <span className="font-semibold text-slate-900 bg-indigo-50 px-2 py-0.5 rounded">
                {d.count}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function StatBox({
  label,
  value,
  testid,
}: {
  label: string
  value: number
  testid: string
}) {
  return (
    <div
      className="text-center py-2 rounded-lg bg-slate-50 border border-slate-100"
      data-testid={testid}
    >
      <p className="text-lg font-bold text-slate-900 tracking-tight">{value.toLocaleString()}</p>
      <p className="text-[10px] text-slate-500 font-medium mt-0.5">{label}</p>
    </div>
  )
}

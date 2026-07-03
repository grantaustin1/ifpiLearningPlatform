/**
 * Documents tab (Iter 30e).
 *
 * Renders the /api/admin/docs manifest and lets Owners/Admins download
 * each IFPI manual as a PDF (server-rendered from the source .md via
 * xhtml2pdf, cached for 1 h). Also offers a raw markdown download for
 * users who want to import the docs into Notion/Confluence.
 */
import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { FileText, Download, RefreshCw, Sparkles, FileCode2 } from 'lucide-react'
import { toast } from 'sonner'

type DocMeta = {
  slug: string
  title: string
  subtitle: string
  audience: string
  auto_regenerated: boolean
  source_file: string
  size_bytes: number
  line_count: number
  modified_at: number
}

const fmtBytes = (n: number) => n < 1024 ? `${n} B` : n < 1_048_576 ? `${(n/1024).toFixed(1)} KB` : `${(n/1_048_576).toFixed(1)} MB`
const fmtWhen = (ts: number) => new Date(ts * 1000).toLocaleString(undefined,
  { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })

export function DocumentsTab() {
  const [docs, setDocs] = useState<DocMeta[]>([])
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    api.get('/admin/docs')
      .then(r => setDocs(r.data.documents || []))
      .catch(() => toast.error('Could not load documents manifest'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  // Streams the PDF via authenticated fetch (axios blob response), then
  // triggers a browser download. Doing it this way instead of a plain
  // `<a href>` because the endpoint is behind the JWT.
  const downloadPdf = async (slug: string, variant: 'pdf' | 'raw') => {
    setDownloading(`${slug}:${variant}`)
    try {
      const res = await api.get(`/admin/docs/${slug}/${variant}`, { responseType: 'blob' })
      const cd = (res.headers['content-disposition'] || '') as string
      const match = cd.match(/filename="?([^";]+)"?/)
      const suggested = match?.[1] || `${slug}.${variant === 'pdf' ? 'pdf' : 'md'}`
      const blob = new Blob([res.data],
        { type: variant === 'pdf' ? 'application/pdf' : 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = suggested
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      toast.success(`Downloaded ${suggested}`)
    } catch (e: any) {
      toast.error(e?.response?.data?.error?.message ||
                  e?.response?.data?.detail ||
                  'Download failed')
    } finally {
      setDownloading(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16" data-testid="docs-tab-loading">
        <div className="w-6 h-6 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="bg-white rounded-2xl shadow-sm p-6" data-testid="docs-tab">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <FileText className="h-5 w-5 text-indigo-500" />
            Documentation Library
          </h2>
          <p className="text-slate-500 text-sm mt-1">
            Download the IFPI manuals as PDF for your team, auditors or new admins.
            {' '}
            <span className="text-indigo-600">Auto-regenerated</span> docs re-render
            automatically as the platform evolves — you always get the freshest copy.
          </p>
        </div>
        <button
          onClick={load}
          data-testid="docs-refresh-btn"
          className="inline-flex items-center gap-2 border border-slate-200 hover:bg-slate-50 text-sm font-medium px-3 py-1.5 rounded-lg text-slate-700"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </button>
      </div>

      {docs.length === 0 && (
        <div className="text-center py-16 text-slate-400 text-sm" data-testid="docs-empty">
          No documents available.
        </div>
      )}

      <ul className="space-y-3">
        {docs.map(doc => (
          <li
            key={doc.slug}
            data-testid={`doc-${doc.slug}`}
            className="border border-slate-200 rounded-xl p-4 hover:border-indigo-200 hover:shadow-sm transition"
          >
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center flex-shrink-0">
                <FileText className="h-5 w-5 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-base font-semibold text-slate-900">{doc.title}</h3>
                  {doc.auto_regenerated && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 uppercase tracking-wide"
                          data-testid={`doc-${doc.slug}-auto-badge`}>
                      <Sparkles className="h-2.5 w-2.5" /> Auto-regenerated
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-500 mt-0.5">{doc.subtitle}</p>
                <div className="mt-2 flex items-center gap-x-4 gap-y-1 flex-wrap text-xs text-slate-400">
                  <span><span className="text-slate-500">Audience:</span> {doc.audience}</span>
                  <span>{doc.line_count.toLocaleString()} lines</span>
                  <span>{fmtBytes(doc.size_bytes)}</span>
                  <span>Updated {fmtWhen(doc.modified_at)}</span>
                </div>
              </div>
              <div className="flex flex-col gap-1.5 flex-shrink-0">
                <button
                  onClick={() => downloadPdf(doc.slug, 'pdf')}
                  disabled={downloading === `${doc.slug}:pdf`}
                  data-testid={`doc-${doc.slug}-pdf-btn`}
                  className="inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg disabled:opacity-50 min-w-[110px] justify-center"
                >
                  <Download className="h-3.5 w-3.5" />
                  {downloading === `${doc.slug}:pdf` ? 'Rendering…' : 'Download PDF'}
                </button>
                <button
                  onClick={() => downloadPdf(doc.slug, 'raw')}
                  disabled={downloading === `${doc.slug}:raw`}
                  data-testid={`doc-${doc.slug}-md-btn`}
                  className="inline-flex items-center gap-1.5 border border-slate-200 hover:bg-slate-50 text-xs font-medium px-3 py-1 rounded-lg text-slate-600 disabled:opacity-50 justify-center"
                >
                  <FileCode2 className="h-3 w-3" />
                  {downloading === `${doc.slug}:raw` ? '…' : 'Markdown'}
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-6 pt-4 border-t border-slate-100 text-xs text-slate-400">
        PDFs are generated on demand from the source markdown and cached for 1 hour.
        Auto-regenerated docs stay in sync with the live platform via the{' '}
        <code className="bg-slate-100 px-1 rounded">build_docs.py</code> pipeline.
      </div>
    </div>
  )
}

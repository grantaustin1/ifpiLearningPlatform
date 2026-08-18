import { useEffect, useState } from 'react'
import { useSearchParams, useParams } from 'react-router-dom'
import axios from 'axios'
import { API_URL } from 'lib/env'
import { BookOpen, CheckCircle2, XCircle, Search, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { usePrompt } from 'components/PromptDialog'

interface Item { id: number; title: string; description?: string; category?: string; duration_minutes?: number }
interface Cert {
  code: string; type: string; issued_at: string | null; score: number | null;
  holder_name: string; course_title: string | null; organization_name: string | null;
}

export default function PublicCatalogPage() {
  const params = useParams()
  const isVerifyRoute = window.location.pathname.startsWith('/verify') || !!params.code
  const [tab, setTab] = useState<'catalog' | 'verify'>(isVerifyRoute ? 'verify' : 'catalog')
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50/30">
      <header className="border-b border-slate-200 bg-white px-8 py-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BookOpen className="text-indigo-600" />
          <div>
            <h1 className="text-xl font-bold text-slate-900">IFPI Learning</h1>
            <p className="text-xs text-slate-500">Public catalog \u00b7 certificate verification</p>
          </div>
        </div>
        <nav className="flex gap-2 bg-slate-100 rounded-lg p-1">
          <button onClick={() => setTab('catalog')} data-testid="pub-tab-catalog"
            className={`px-4 py-1.5 text-xs font-semibold rounded ${tab === 'catalog' ? 'bg-white text-indigo-700 shadow' : 'text-slate-600'}`}>
            Catalog
          </button>
          <button onClick={() => setTab('verify')} data-testid="pub-tab-verify"
            className={`px-4 py-1.5 text-xs font-semibold rounded ${tab === 'verify' ? 'bg-white text-indigo-700 shadow' : 'text-slate-600'}`}>
            Verify certificate
          </button>
        </nav>
      </header>
      <main className="max-w-5xl mx-auto p-8">
        {tab === 'catalog' ? <CatalogTab /> : <VerifyTab />}
      </main>
    </div>
  )
}

function CatalogTab() {
  const [items, setItems] = useState<Item[]>([])
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(true)
  const [tokenInput, setTokenInput] = useState<string>(() => localStorage.getItem('ifpi_public_token') || '')
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true); setError(null)
    try {
      const headers: any = tokenInput ? { Authorization: `Bearer ${tokenInput}` } : {}
      const r = await axios.get(`${API_URL}/api/public/catalog`, {
        headers, params: q ? { q } : undefined,
      })
      setItems(r.data.items)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Load failed. You may need an API token with `read:catalog` scope.')
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const saveToken = () => {
    localStorage.setItem('ifpi_public_token', tokenInput)
    load()
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3" data-testid="pub-catalog-search">
        <label className="text-xs font-semibold text-slate-600">API token (with <code>read:catalog</code> scope)</label>
        <div className="flex gap-2">
          <input value={tokenInput} onChange={e => setTokenInput(e.target.value)}
            placeholder="ifpi_\u2026"
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono"
            data-testid="pub-catalog-token-input" />
          <button onClick={saveToken}
            data-testid="pub-catalog-save-token"
            className="text-xs bg-slate-800 hover:bg-slate-700 text-white px-4 rounded-lg font-semibold">Load</button>
        </div>
        <label className="block text-xs font-semibold text-slate-600 pt-2">Search</label>
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="h-4 w-4 absolute left-3 top-3 text-slate-400" />
            <input value={q} onChange={e => setQ(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && load()}
              placeholder="Search course title or description\u2026"
              className="w-full border border-slate-300 rounded-lg pl-9 pr-3 py-2 text-sm"
              data-testid="pub-catalog-search-input" />
          </div>
          <button onClick={load}
            data-testid="pub-catalog-search-btn"
            className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white px-4 rounded-lg font-semibold">Search</button>
        </div>
      </div>

      {error && <div className="bg-rose-50 border border-rose-200 text-rose-800 rounded-xl p-4 text-sm" data-testid="pub-catalog-error">{error}</div>}
      {loading ? (
        <div className="text-sm text-slate-500">Loading\u2026</div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4" data-testid="pub-catalog-list">
          {items.map(c => (
            <div key={c.id} className="bg-white rounded-2xl border border-slate-200 p-5 hover:shadow-lg transition" data-testid={`pub-course-${c.id}`}>
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-indigo-600 font-bold">
                {c.category || 'Course'}
              </div>
              <h3 className="mt-1 text-base font-semibold text-slate-900">{c.title}</h3>
              {c.description && <p className="mt-1 text-xs text-slate-500 line-clamp-2">{c.description}</p>}
              <div className="mt-3 flex items-center gap-3 text-[11px] text-slate-400">
                <span>{c.duration_minutes || 0} min</span>
              </div>
            </div>
          ))}
          {!items.length && <p className="col-span-full text-sm text-slate-500">No courses found.</p>}
        </div>
      )}
    </div>
  )
}

function VerifyTab() {
  const [search] = useSearchParams()
  const params = useParams()
  const initialCode = params.code || search.get('code') || ''
  const [code, setCode] = useState(initialCode)
  const [cert, setCert] = useState<Cert | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [busy, setBusy] = useState(false)
  const prompt = usePrompt()

  const verify = async () => {
    if (!code.trim()) return
    setBusy(true); setCert(null); setNotFound(false)
    try {
      const r = await axios.get(`${API_URL}/api/public/certificates/verify/${encodeURIComponent(code.trim())}`)
      setCert(r.data)
    } catch (e: any) {
      if (e?.response?.status === 404) setNotFound(true)
      else if (e?.response?.status === 429) toast.error('Too many verification attempts \u2014 please try again in a minute.')
    } finally { setBusy(false) }
  }

  useEffect(() => { if (initialCode) verify() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-2 text-indigo-800">
          <ShieldCheck className="h-5 w-5" />
          <h2 className="font-semibold">Verify a certificate</h2>
        </div>
        <p className="text-xs text-slate-500">
          Paste the certificate code (e.g. from a physical or PDF certificate) to confirm it's authentic.
        </p>
        <div className="flex gap-2">
          <input value={code} onChange={e => setCode(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && verify()}
            placeholder="Certificate code\u2026"
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono"
            data-testid="pub-cert-code-input" />
          <button onClick={verify} disabled={busy}
            data-testid="pub-cert-verify-btn"
            className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white text-sm font-semibold px-5 rounded-lg">
            {busy ? 'Checking\u2026' : 'Verify'}
          </button>
        </div>
      </div>

      {cert && (
        <div className="bg-emerald-50 border-2 border-emerald-200 rounded-2xl p-6 space-y-3" data-testid="pub-cert-result-valid">
          <div className="flex items-center gap-2 text-emerald-800">
            <CheckCircle2 className="h-6 w-6" />
            <h3 className="text-lg font-bold">Certificate verified</h3>
          </div>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3">
            {[
              ['Holder', cert.holder_name],
              ['Course', cert.course_title || '\u2014'],
              ['Type', cert.type],
              ['Issued', cert.issued_at ? new Date(cert.issued_at).toLocaleDateString() : '\u2014'],
              ['Score', cert.score != null ? `${cert.score}%` : '\u2014'],
              ['Issuing organization', cert.organization_name || '\u2014'],
              ['Code', cert.code],
            ].map(([k, v]) => (
              <div key={k}>
                <dt className="text-[11px] uppercase tracking-wider text-emerald-700 font-semibold">{k}</dt>
                <dd className="text-sm text-slate-800 font-medium">{v}</dd>
              </div>
            ))}
          </dl>
          <div className="pt-3 flex items-center gap-2">
            <button
              onClick={() => {
                const url = `${window.location.origin}/verify/${encodeURIComponent(cert.code)}`
                const showManualCopy = () => prompt({
                  title: 'Copy this verify link',
                  description: 'Your browser blocked automatic copy. Select the text and copy it manually.',
                  defaultValue: url,
                  confirmLabel: 'Done',
                  cancelLabel: 'Close',
                })
                if (navigator.clipboard) {
                  navigator.clipboard.writeText(url).then(
                    () => toast.success('Verify link copied \u00b7 share it with recruiters'),
                    () => showManualCopy(),
                  )
                } else {
                  showManualCopy()
                }
              }}
              data-testid="pub-cert-copy-link"
              className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-4 py-2 rounded-lg inline-flex items-center gap-2"
            >
              🔗 Copy shareable verify link
            </button>
            <span className="text-[11px] text-slate-500">Send this to recruiters \u2014 they can verify without an IFPI account.</span>
          </div>
        </div>
      )}
      {notFound && (
        <div className="bg-rose-50 border-2 border-rose-200 rounded-2xl p-6 flex items-start gap-3" data-testid="pub-cert-result-invalid">
          <XCircle className="h-6 w-6 text-rose-600 flex-shrink-0" />
          <div>
            <h3 className="font-bold text-rose-800">Certificate not found</h3>
            <p className="text-sm text-rose-700 mt-1">This code doesn't match any certificate we've issued. Double-check the code or contact IFPI.</p>
          </div>
        </div>
      )}
    </div>
  )
}

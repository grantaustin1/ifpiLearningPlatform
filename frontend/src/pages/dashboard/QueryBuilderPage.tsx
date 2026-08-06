/**
 * Iter 30q — AI Query Builder v1 admin UI.
 *
 * Simple ask-a-question interface. Shows the LLM-generated SQL alongside
 * the results so admins can validate before trusting. "Copy SQL" button
 * for admins who want to hand it to their BI tool.
 */
import { useState } from 'react'
import { api } from 'lib/api'
import { Sparkles, Copy, Check, AlertTriangle, Database } from 'lucide-react'

type Result = {
  sql: string
  reason: string
  rows: any[]
  row_count: number
  truncated: boolean
}

const SAMPLE_QUESTIONS = [
  'How many published courses do we have?',
  'List the top 5 learners by points',
  'How many certificates were issued this month?',
  'Which courses have the most completed enrollments?',
]

export default function QueryBuilderPage() {
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const run = async (question?: string) => {
    const query = (question ?? q).trim()
    if (!query) return
    setBusy(true); setError(''); setResult(null)
    try {
      const r = await api.post('/admin/query-builder/build', { question: query })
      setResult(r.data)
      if (question) setQ(question)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Query failed')
    } finally { setBusy(false) }
  }

  const copySQL = () => {
    if (!result) return
    navigator.clipboard.writeText(result.sql)
    setCopied(true); setTimeout(() => setCopied(false), 1500)
  }

  const cols = result?.rows[0] ? Object.keys(result.rows[0]) : []

  return (
    <div className="max-w-5xl mx-auto space-y-6 p-6" data-testid="query-builder-page">
      <header>
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-lg bg-gradient-to-br from-indigo-600 to-fuchsia-600 flex items-center justify-center">
            <Database className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">AI Query Builder</h1>
            <p className="text-sm text-slate-500">
              Ask any analytics question in plain English. Answers are scoped to your organisation and read-only.
            </p>
          </div>
        </div>
      </header>

      <div className="bg-white border border-slate-200 rounded-2xl p-5">
        <textarea
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="e.g. Which learners completed 'IFPI Fundamentals' last month?"
          rows={3}
          data-testid="query-builder-input"
          className="w-full px-4 py-3 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
        />
        <div className="flex items-center justify-between mt-3">
          <div className="flex flex-wrap gap-1.5">
            {SAMPLE_QUESTIONS.map(s => (
              <button key={s} onClick={() => run(s)} disabled={busy}
                      className="text-[11px] text-slate-500 border border-slate-200 hover:border-indigo-300 hover:text-indigo-700 rounded-full px-2.5 py-1 disabled:opacity-40">
                {s}
              </button>
            ))}
          </div>
          <button
            onClick={() => run()}
            disabled={busy || !q.trim()}
            data-testid="query-builder-run"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-sm font-semibold px-5 py-2 rounded-lg shadow-sm">
            {busy
              ? <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              : <><Sparkles className="h-4 w-4" /> Ask</>}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3" data-testid="query-builder-error">
          <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="bg-slate-900 text-slate-100 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[11px] uppercase font-semibold text-slate-400 tracking-wide">Generated SQL</p>
              <button onClick={copySQL}
                      data-testid="query-copy-sql"
                      className="text-[11px] font-semibold text-slate-300 hover:text-white inline-flex items-center gap-1">
                {copied ? <><Check className="h-3 w-3" /> Copied</> : <><Copy className="h-3 w-3" /> Copy</>}
              </button>
            </div>
            <pre className="text-xs font-mono whitespace-pre-wrap break-all leading-relaxed" data-testid="query-sql">{result.sql}</pre>
            {result.reason && (
              <p className="text-[11px] text-slate-400 mt-2 italic">
                {result.reason}
              </p>
            )}
          </div>

          <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden" data-testid="query-results">
            <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-800">
                {result.row_count} row{result.row_count === 1 ? '' : 's'}
                {result.truncated && <span className="ml-2 text-xs text-amber-700">(auto-limited to 500)</span>}
              </p>
            </div>
            {result.rows.length === 0 ? (
              <p className="p-8 text-center text-sm text-slate-400">No rows matched.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      {cols.map(c => (
                        <th key={c} className="text-left px-4 py-2 text-[11px] uppercase font-semibold text-slate-500 tracking-wide border-b border-slate-100">
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, i) => (
                      <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                        {cols.map(c => (
                          <td key={c} className="px-4 py-2 text-slate-700">
                            {row[c] === null || row[c] === undefined
                              ? <span className="text-slate-300 italic">null</span>
                              : String(row[c])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

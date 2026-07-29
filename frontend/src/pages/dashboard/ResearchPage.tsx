import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { Sparkles, Loader2, ExternalLink, CheckCircle2, AlertTriangle, Clock, FileText } from 'lucide-react'
import { toast } from 'sonner'

interface Job {
  id: number
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | string
  input?: { query?: string; depth?: string; course_id?: number | null }
  output?: { source_document_id?: number; chunk_count?: number; source_count?: number }
  error_log?: string | null
  created_at?: string | null
  completed_at?: string | null
}

const statusPill: Record<string, string> = {
  PENDING:   'bg-slate-200 text-slate-700',
  RUNNING:   'bg-amber-200 text-amber-800 animate-pulse',
  COMPLETED: 'bg-emerald-200 text-emerald-800',
  FAILED:    'bg-rose-200 text-rose-800',
}

export default function ResearchPage() {
  const [query, setQuery] = useState('')
  const [depth, setDepth] = useState<'quick' | 'deep'>('quick')
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [activePolls, setActivePolls] = useState<Record<number, boolean>>({})

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.get('/authoring/research')
      setJobs(r.data.items || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const pollJob = async (id: number) => {
    setActivePolls(p => ({ ...p, [id]: true }))
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 2500))
      try {
        const r = await api.get(`/authoring/research/${id}`)
        setJobs(js => js.map(j => (j.id === id ? { ...j, ...r.data } : j)))
        if (r.data.status === 'COMPLETED' || r.data.status === 'FAILED') break
      } catch (e) {
        // Poll may fail transiently (network flap, backend restart) —
        // continue the loop so we retry on the next tick. Log for
        // debugging without spamming the user.
        console.debug('research poll failed, will retry', id, e)
      }
    }
    setActivePolls(p => ({ ...p, [id]: false }))
  }

  const start = async () => {
    if (query.trim().length < 3) return toast.error('Query must be at least 3 characters')
    setStarting(true)
    try {
      const r = await api.post('/authoring/research/start', { query: query.trim(), depth })
      toast.success('Research started')
      setQuery('')
      await load()
      pollJob(r.data.job_id)
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      if (typeof detail === 'object' && detail?.code === 'tavily_key_missing') {
        toast.error('Add TAVILY_API_KEY to backend/.env and restart')
      } else {
        toast.error(String(detail ?? 'Failed to start research'))
      }
    } finally { setStarting(false) }
  }

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
            <Sparkles className="text-indigo-500" /> Deep research
          </h1>
          <p className="text-slate-500 text-sm mt-1 max-w-2xl">
            Runs a multi-source web search via Tavily, synthesises a briefing document,
            and stores it in your source library so the AI tutor can cite it.
          </p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4" data-testid="research-form">
        <label className="text-sm font-semibold text-slate-700">Research query</label>
        <div className="flex flex-col md:flex-row gap-3">
          <input
            data-testid="research-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='e.g. "latest copyright enforcement trends in streaming, 2025"'
            className="flex-1 border border-slate-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <select
            data-testid="research-depth"
            value={depth}
            onChange={(e) => setDepth(e.target.value as 'quick' | 'deep')}
            className="border border-slate-300 rounded-lg px-4 py-2.5 text-sm bg-white"
          >
            <option value="quick">Quick (≤ 90s)</option>
            <option value="deep">Deep (≤ 6 min)</option>
          </select>
          <button
            data-testid="research-start-btn"
            onClick={start}
            disabled={starting || query.trim().length < 3}
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white px-5 py-2.5 rounded-lg text-sm font-semibold shadow-md shadow-indigo-500/20 transition"
          >
            {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {starting ? 'Starting…' : 'Start research'}
          </button>
        </div>
        <p className="text-xs text-slate-500">
          Powered by Tavily. Results become a `RESEARCH_NOTE` source document in your library.
        </p>
      </div>

      <div className="space-y-3" data-testid="research-history">
        <h2 className="text-lg font-semibold text-slate-700">Recent runs</h2>
        {loading ? (
          <div className="text-sm text-slate-500 flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
        ) : jobs.length === 0 ? (
          <div className="bg-white rounded-2xl border border-dashed border-slate-300 py-10 text-center text-slate-500 text-sm">
            No research runs yet. Start one above.
          </div>
        ) : jobs.map(j => (
          <div key={j.id} className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5" data-testid={`research-job-${j.id}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-3">
                  <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${statusPill[j.status] || 'bg-slate-100 text-slate-700'}`}>
                    {j.status}
                  </span>
                  <span className="text-[11px] text-slate-500 uppercase tracking-wide">{j.input?.depth || 'quick'}</span>
                  {activePolls[j.id] && <Loader2 className="h-3.5 w-3.5 text-indigo-500 animate-spin" />}
                </div>
                <p className="mt-2 text-sm font-medium text-slate-800 break-words">{j.input?.query || '—'}</p>
                {j.output && (
                  <div className="mt-2 flex items-center gap-2 text-xs text-slate-600">
                    <FileText className="h-3.5 w-3.5" />
                    Created source doc #{j.output.source_document_id} · {j.output.chunk_count} chunks · {j.output.source_count} sources
                  </div>
                )}
                {j.error_log && (
                  <div className="mt-2 flex items-start gap-2 text-xs text-rose-700 bg-rose-50 p-2 rounded-lg">
                    <AlertTriangle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
                    <span className="break-words">{j.error_log}</span>
                  </div>
                )}
                <div className="mt-2 flex items-center gap-3 text-[11px] text-slate-500">
                  <Clock className="h-3 w-3" />
                  {j.created_at ? new Date(j.created_at).toLocaleString() : ''}
                  {j.completed_at && (
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                      {new Date(j.completed_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
              {j.status !== 'COMPLETED' && j.status !== 'FAILED' && !activePolls[j.id] && (
                <button
                  onClick={() => pollJob(j.id)}
                  className="text-xs text-indigo-600 hover:underline flex items-center gap-1"
                  data-testid={`research-poll-${j.id}`}
                >
                  <ExternalLink className="h-3 w-3" /> Poll
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

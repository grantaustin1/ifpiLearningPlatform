import { useEffect, useState } from 'react'
<<<<<<< HEAD
import { useConfirm } from 'components/ConfirmDialog'
=======
>>>>>>> origin/main
import { api } from 'lib/api'
import { Upload, Play, RefreshCw, FolderInput, CheckCircle2, XCircle, AlertCircle, Clock, Undo2 } from 'lucide-react'
import { toast } from 'sonner'

interface ImportJob {
  id: number
  job_type: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'PARTIAL' | 'FAILED' | 'ROLLED_BACK'
  source_path: string | null
  total_items: number
  processed_items: number
  failed_items: number
  percent: number
  results: any
  error_log: string | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
}

const STATUS_META: Record<string, { icon: any; cls: string; label: string }> = {
  PENDING:     { icon: Clock,         cls: 'bg-slate-100 text-slate-700 border-slate-200',     label: 'Pending' },
  RUNNING:     { icon: RefreshCw,     cls: 'bg-indigo-50 text-indigo-700 border-indigo-200',   label: 'Running' },
  COMPLETED:   { icon: CheckCircle2,  cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', label: 'Completed' },
  PARTIAL:     { icon: AlertCircle,   cls: 'bg-amber-50 text-amber-700 border-amber-200',      label: 'Partial' },
  FAILED:      { icon: XCircle,       cls: 'bg-rose-50 text-rose-700 border-rose-200',         label: 'Failed' },
  ROLLED_BACK: { icon: Undo2,         cls: 'bg-slate-100 text-slate-500 border-slate-200 line-through', label: 'Rolled back' },
}

export default function ImportsPage() {
<<<<<<< HEAD
  const confirm = useConfirm()
=======
>>>>>>> origin/main
  const [jobs, setJobs] = useState<ImportJob[]>([])
  const [loading, setLoading] = useState(true)
  const [showRun, setShowRun] = useState(false)
  const [expandedJob, setExpandedJob] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.get('/admin/imports')
      setJobs(r.data.items)
    } finally { setLoading(false) }
  }

  const rollback = async (jobId: number) => {
<<<<<<< HEAD
    if (!(await confirm({
      title: 'Roll back this import?',
      description: 'All courses and learning paths it created will be permanently deleted. This cannot be undone.',
      confirmLabel: 'Roll back',
      variant: 'danger',
    }))) return
=======
    if (!window.confirm('Roll back this import? All courses and learning paths it created will be permanently deleted. This cannot be undone.')) return
>>>>>>> origin/main
    try {
      const r = await api.post(`/admin/imports/${jobId}/rollback`)
      toast.success(`Rolled back — deleted ${r.data.deleted_courses} courses, ${r.data.deleted_paths} paths`)
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Rollback failed')
    }
  }

  useEffect(() => { load() }, [])

  // Poll while any job is running
  useEffect(() => {
    const anyRunning = jobs.some(j => j.status === 'RUNNING' || j.status === 'PENDING')
    if (!anyRunning) return
    const t = setInterval(load, 2000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.map(j => j.status).join(',')])

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <FolderInput className="h-6 w-6 text-indigo-600" /> Content imports
          </h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">
            Bulk-import courses, slides, exams, and learning paths from a server-side directory tree. Each run is tracked end-to-end with progress and error reports.
          </p>
        </div>
        <button onClick={() => setShowRun(true)} data-testid="run-import-btn"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">
          <Play className="h-4 w-4" /> Run import
        </button>
      </div>

      {loading ? (
        <div className="text-sm text-slate-400">Loading…</div>
      ) : jobs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/50 p-10 text-center">
          <Upload className="h-10 w-10 text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-600 font-medium">No imports yet</p>
          <p className="text-xs text-slate-400 mt-1">Upload a content tree onto the server, then click &quot;Run import&quot; with the directory path.</p>
        </div>
      ) : (
        <div className="space-y-3" data-testid="imports-list">
          {jobs.map(j => {
            const meta = STATUS_META[j.status] || STATUS_META.PENDING
            const Icon = meta.icon
            return (
              <div key={j.id} className="rounded-xl border border-slate-200 bg-white" data-testid={`import-row-${j.id}`}>
                <div className="p-4 flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border ${meta.cls}`}>
                        <Icon className={`h-3 w-3 ${j.status === 'RUNNING' ? 'animate-spin' : ''}`} /> {meta.label}
                      </span>
                      <span className="text-[10px] uppercase font-mono text-slate-400">{j.job_type}</span>
                      <span className="text-[10px] text-slate-400 ml-auto">
                        {j.created_at ? new Date(j.created_at).toLocaleString() : ''}
                      </span>
                    </div>
                    <div className="font-mono text-xs text-slate-700 mt-1.5 truncate" title={j.source_path || ''}>{j.source_path}</div>
                    <div className="mt-2 flex items-center gap-3">
                      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all ${j.status === 'FAILED' ? 'bg-rose-500' : j.failed_items > 0 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                          style={{ width: `${j.percent}%` }}
                          data-testid={`import-progress-${j.id}`}
                        />
                      </div>
                      <span className="text-xs font-mono text-slate-600 whitespace-nowrap">
                        {j.processed_items}/{j.total_items} ({j.percent}%)
                      </span>
                      {j.failed_items > 0 && (
                        <span className="text-xs font-semibold text-rose-600">{j.failed_items} failed</span>
                      )}
                    </div>
                  </div>
                  <button onClick={() => setExpandedJob(expandedJob === j.id ? null : j.id)}
                    data-testid={`import-expand-${j.id}`}
                    className="text-xs border border-slate-200 hover:bg-slate-50 px-2.5 py-1.5 rounded-lg whitespace-nowrap">
                    {expandedJob === j.id ? 'Hide details' : 'Show details'}
                  </button>
                  {(j.status === 'COMPLETED' || j.status === 'PARTIAL') &&
                    ((j.results?.courses?.length || 0) + (j.results?.paths?.length || 0)) > 0 && (
                    <button onClick={() => rollback(j.id)}
                      data-testid={`import-rollback-${j.id}`}
                      title="Delete every course and path this import created"
                      className="inline-flex items-center gap-1 text-xs border border-rose-200 text-rose-700 hover:bg-rose-50 px-2.5 py-1.5 rounded-lg whitespace-nowrap">
                      <Undo2 className="h-3.5 w-3.5" /> Roll back
                    </button>
                  )}
                </div>
                {expandedJob === j.id && (
                  <div className="border-t border-slate-100 px-4 py-3 bg-slate-50/40 text-xs space-y-2">
                    {j.results?.courses?.length > 0 && (
                      <div>
                        <div className="font-semibold text-slate-700 mb-1">Courses ({j.results.courses.length})</div>
                        <ul className="space-y-0.5 ml-3">
                          {j.results.courses.map((c: any, i: number) => (
                            <li key={i} className="text-slate-600">
                              <span className="text-emerald-600">✓</span> {c.title}
                              <span className="text-slate-400 ml-2 font-mono">{c.slides} slides · {c.exams} exams</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {j.results?.paths?.length > 0 && (
                      <div>
                        <div className="font-semibold text-slate-700 mb-1">Learning paths ({j.results.paths.length})</div>
                        <ul className="space-y-0.5 ml-3">
                          {j.results.paths.map((p: any, i: number) => (
                            <li key={i} className="text-slate-600">
                              <span className="text-emerald-600">✓</span> {p.title}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {j.results?.errors?.length > 0 && (
                      <div>
                        <div className="font-semibold text-rose-700 mb-1">Errors ({j.results.errors.length})</div>
                        <ul className="space-y-0.5 ml-3">
                          {j.results.errors.map((e: any, i: number) => (
                            <li key={i} className="text-rose-700 font-mono break-all">
                              [{e.kind}] {e.path}: {e.error}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {j.error_log && (
                      <pre className="bg-rose-50 text-rose-800 p-2 rounded text-[10px] whitespace-pre-wrap break-words">
                        {j.error_log}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {showRun && (
        <RunImportModal onClose={() => setShowRun(false)}
          onStarted={() => { setShowRun(false); load() }} />
      )}
    </div>
  )
}


function RunImportModal({ onClose, onStarted }: { onClose: () => void; onStarted: () => void }) {
  const [tab, setTab] = useState<'zip' | 'path'>('zip')
  const [path, setPath] = useState('/app/migration-staging')
  const [publish, setPublish] = useState(false)
  const [running, setRunning] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)

  const runPath = async () => {
    if (!path.trim()) { toast.error('Enter a server-side directory path'); return }
    setRunning(true)
    try {
      await api.post('/admin/imports/run', {
        source_path: path.trim(),
        publish_on_import: publish,
        job_type: 'FULL_MIGRATION',
      })
      toast.success('Import started — watch progress below')
      onStarted()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Could not start import')
    } finally { setRunning(false) }
  }

  const runZip = async () => {
    if (!file) { toast.error('Drop or choose a .zip file first'); return }
    if (!file.name.toLowerCase().endsWith('.zip')) {
      toast.error('Only .zip archives are accepted'); return
    }
    setRunning(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      await api.post(
        `/admin/imports/upload-zip?publish_on_import=${publish}&job_type=FULL_MIGRATION`,
        fd,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      toast.success(`Uploaded ${file.name} — extracting & importing now`)
      onStarted()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Upload failed')
    } finally { setRunning(false) }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose} data-testid="run-import-modal">
      <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-slate-900 mb-1">Run bulk import</h2>
        <p className="text-xs text-slate-500 mb-4">Drop a zipped content tree from your computer, or point to a server-side directory.</p>

        <div className="inline-flex rounded-lg border border-slate-200 p-0.5 mb-4 text-xs">
          <button onClick={() => setTab('zip')} data-testid="tab-zip"
            className={`px-3 py-1.5 rounded-md font-semibold ${tab === 'zip' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-50'}`}>
            Upload .zip
          </button>
          <button onClick={() => setTab('path')} data-testid="tab-path"
            className={`px-3 py-1.5 rounded-md font-semibold ${tab === 'path' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-50'}`}>
            Server path
          </button>
        </div>

        {tab === 'zip' ? (
          <div
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => {
              e.preventDefault(); setDragging(false)
              const f = e.dataTransfer.files?.[0]
              if (f) setFile(f)
            }}
            data-testid="zip-dropzone"
            className={`rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
              dragging ? 'border-indigo-500 bg-indigo-50/60' : 'border-slate-300 bg-slate-50/40'
            }`}>
            <Upload className="h-8 w-8 text-slate-400 mx-auto mb-2" />
            {file ? (
              <>
                <p className="text-sm font-semibold text-slate-800">{file.name}</p>
                <p className="text-[11px] text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                <button onClick={() => setFile(null)} className="text-xs text-rose-600 hover:underline mt-1">Remove</button>
              </>
            ) : (
              <>
                <p className="text-sm text-slate-700 font-medium">Drag a .zip file here</p>
                <p className="text-[11px] text-slate-400 mt-0.5">…or click below to choose</p>
              </>
            )}
            <input type="file" accept=".zip,application/zip" id="zip-file-input"
              data-testid="zip-file-input"
              className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) setFile(f) }} />
            <label htmlFor="zip-file-input"
              className="inline-block mt-3 text-xs font-semibold border border-slate-200 hover:bg-white px-3 py-1.5 rounded-lg cursor-pointer">
              Choose file
            </label>
            <p className="text-[10px] text-slate-400 mt-2">Max 200 MB. Use SCP/mount for larger trees.</p>
          </div>
        ) : (
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Server-side path *</label>
            <input value={path} onChange={e => setPath(e.target.value)} placeholder="/app/migration-staging"
              data-testid="import-source-path"
              className="w-full font-mono text-xs px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/30" />
            <p className="text-[10px] text-slate-400 mt-1">Must contain `courses/` and/or `paths/` subdirectories.</p>
          </div>
        )}

        <label className="flex items-center gap-2 cursor-pointer mt-4">
          <input type="checkbox" checked={publish} onChange={e => setPublish(e.target.checked)}
            data-testid="import-publish-toggle"
            className="rounded accent-indigo-500 h-4 w-4" />
          <span className="text-sm text-slate-700">Publish courses + paths immediately (otherwise: DRAFT)</span>
        </label>

        <div className="flex justify-end gap-2 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancel</button>
          <button onClick={tab === 'zip' ? runZip : runPath} disabled={running} data-testid="import-start-btn"
            className="inline-flex items-center gap-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2 rounded-lg">
            {running ? 'Starting…' : <><Play className="h-4 w-4" /> Start import</>}
          </button>
        </div>
      </div>
    </div>
  )
}

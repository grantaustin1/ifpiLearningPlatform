import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { KeyRound, Plus, X, Copy, ShieldOff, Trash2, ShieldCheck, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'

interface Token {
  id: number
  name: string
  prefix: string
  scopes: string[]
  is_active: boolean
  last_used_at: string | null
  expires_at: string | null
  created_at: string | null
}

const SCOPES = ['LEARNER', 'INSTRUCTOR', 'ADMIN', 'SUPER_ADMIN', 'read:catalog']

export default function ApiTokensPage() {
  const [tokens, setTokens] = useState<Token[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [justCreated, setJustCreated] = useState<{ token: string; name: string } | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.get('/admin/api-tokens')
      setTokens(r.data.items)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const revoke = async (id: number) => {
    if (!window.confirm('Revoke this token? Any external system using it will lose access immediately.')) return
    await api.post(`/admin/api-tokens/${id}/revoke`)
    toast.success('Token revoked')
    load()
  }
  const remove = async (id: number) => {
    if (!window.confirm('Delete this token row permanently?')) return
    await api.delete(`/admin/api-tokens/${id}`)
    toast.success('Token deleted')
    load()
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <KeyRound className="h-6 w-6 text-indigo-600" /> API tokens
          </h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">
            Long-lived bearer tokens for server-to-server access — perfect for LRS bridges, SSO middleware, or CI scripts that need to call IFPI without storing an admin password.
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} data-testid="create-token-btn"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">
          <Plus className="h-4 w-4" /> New token
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-slate-400">Loading…</p>
      ) : tokens.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/50 p-10 text-center">
          <KeyRound className="h-10 w-10 text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-600 font-medium">No API tokens yet</p>
          <p className="text-xs text-slate-400 mt-1">Create one to authenticate external systems.</p>
        </div>
      ) : (<>
        <UsageChart />
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden" data-testid="tokens-list">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-3">Name</th>
                <th className="text-left px-4 py-3">Prefix</th>
                <th className="text-left px-4 py-3">Scopes</th>
                <th className="text-left px-4 py-3">Last used</th>
                <th className="text-left px-4 py-3">Expires</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-right px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {tokens.map(t => (
                <tr key={t.id} className="border-t border-slate-100" data-testid={`token-row-${t.id}`}>
                  <td className="px-4 py-3 font-semibold text-slate-800">{t.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">{t.prefix}…</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1 flex-wrap">
                      {(t.scopes || []).map(s => (
                        <span key={s} className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-100">{s}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{t.last_used_at ? new Date(t.last_used_at).toLocaleString() : 'never'}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">{t.expires_at ? new Date(t.expires_at).toLocaleDateString() : '—'}</td>
                  <td className="px-4 py-3">
                    {t.is_active ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-semibold"><ShieldCheck className="h-3.5 w-3.5" /> Active</span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-rose-600 font-semibold"><ShieldOff className="h-3.5 w-3.5" /> Revoked</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                    {t.is_active && (
                      <button onClick={() => revoke(t.id)} data-testid={`revoke-${t.id}`}
                        className="inline-flex items-center gap-1 text-xs border border-amber-300 text-amber-700 hover:bg-amber-50 px-2 py-1 rounded">
                        <ShieldOff className="h-3 w-3" /> Revoke
                      </button>
                    )}
                    <button onClick={() => remove(t.id)} data-testid={`delete-${t.id}`}
                      className="inline-flex items-center gap-1 text-xs border border-rose-200 text-rose-600 hover:bg-rose-50 px-2 py-1 rounded">
                      <Trash2 className="h-3 w-3" /> Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>)}

      {showCreate && <CreateModal onClose={() => setShowCreate(false)} onCreated={(t) => { setJustCreated(t); setShowCreate(false); load() }} />}
      {justCreated && <RevealModal token={justCreated.token} name={justCreated.name} onClose={() => setJustCreated(null)} />}
    </div>
  )
}


// ── Inline SVG usage chart (Iter P2) ──────────────────────────────
function UsageChart() {
  const [data, setData] = useState<{ series: any[]; by_token: any[]; total_calls: number; total_errors: number } | null>(null)
  useEffect(() => {
    api.get('/admin/api-tokens/analytics/usage?days=30')
      .then(r => setData(r.data))
      .catch(() => setData({ series: [], by_token: [], total_calls: 0, total_errors: 0 }))
  }, [])
  if (!data) return null
  const max = Math.max(1, ...data.series.map((d: any) => d.count))
  const W = 720, H = 140, PAD = 20
  const bw = (W - PAD * 2) / (data.series.length || 1)
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3" data-testid="tokens-usage-chart">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-slate-700">Requests (last 30 days)</h2>
        <div className="text-xs text-slate-500 flex gap-4">
          <span data-testid="tokens-total-calls"><span className="font-bold text-slate-800">{data.total_calls}</span> total</span>
          <span data-testid="tokens-total-errors" className={data.total_errors > 0 ? 'text-rose-600 font-semibold' : ''}>
            {data.total_errors} errors
          </span>
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[140px]" preserveAspectRatio="none">
        {data.series.map((d: any, i: number) => {
          const h = (d.count / max) * (H - PAD * 2)
          const x = PAD + i * bw
          const y = H - PAD - h
          return (
            <g key={d.date}>
              <rect x={x + 1} y={y} width={Math.max(1, bw - 2)} height={Math.max(0, h)}
                fill={d.errors > 0 ? '#f43f5e' : '#4f46e5'} opacity={d.count === 0 ? 0.15 : 0.85}>
                <title>{d.date}: {d.count} calls, {d.errors} errors</title>
              </rect>
            </g>
          )
        })}
        <line x1={PAD} x2={W - PAD} y1={H - PAD} y2={H - PAD} stroke="#e2e8f0" />
      </svg>
      {data.by_token.length > 0 && (
        <div className="pt-2">
          <p className="text-[11px] uppercase font-semibold text-slate-500 tracking-wide mb-2">Top tokens (30d)</p>
          <ul className="space-y-1.5">
            {data.by_token.slice(0, 5).map((t: any) => (
              <li key={t.token_id} className="text-xs flex items-center gap-2" data-testid={`tokens-top-${t.token_id}`}>
                <span className="font-mono text-slate-500 w-20 truncate">{t.prefix}</span>
                <span className="flex-1 truncate text-slate-700">{t.name}</span>
                <span className="tabular-nums font-semibold text-slate-800">{t.count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}


function CreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: (t: { token: string; name: string }) => void }) {
  const [name, setName] = useState('')
  const [scope, setScope] = useState<string>('LEARNER')
  const [expires, setExpires] = useState<number>(90)
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (!name.trim()) { toast.error('Give the token a name'); return }
    setBusy(true)
    try {
      const r = await api.post('/admin/api-tokens', {
        name: name.trim(), scopes: [scope],
        expires_in_days: expires || null,
      })
      onCreated({ token: r.data.token, name: r.data.name })
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Could not create token')
    } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose} data-testid="create-token-modal">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-3 border-b flex items-center justify-between">
          <h3 className="font-semibold text-slate-900">Create API token</h3>
          <button onClick={onClose}><X className="h-5 w-5 text-slate-400" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Name *</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. LRS bridge"
              data-testid="token-name"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Scope</label>
            <select value={scope} onChange={e => setScope(e.target.value)} data-testid="token-scope"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm">
              {SCOPES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <p className="text-[10px] text-slate-400 mt-1">LEARNER is enough for xAPI receivers. ADMIN should be reserved for full-management integrations.</p>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Expires in (days)</label>
            <input type="number" value={expires} onChange={e => setExpires(parseInt(e.target.value) || 0)} min={0} max={365 * 5}
              data-testid="token-expires"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" />
            <p className="text-[10px] text-slate-400 mt-1">Leave 0 for no expiry (not recommended).</p>
          </div>
        </div>
        <div className="px-5 py-3 border-t flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancel</button>
          <button onClick={submit} disabled={busy} data-testid="token-submit"
            className="px-3 py-1.5 text-sm bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold rounded-lg">
            {busy ? 'Creating…' : 'Create token'}
          </button>
        </div>
      </div>
    </div>
  )
}


function RevealModal({ token, name, onClose }: { token: string; name: string; onClose: () => void }) {
  const copy = () => {
    navigator.clipboard.writeText(token)
    toast.success('Token copied to clipboard')
  }
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" data-testid="reveal-modal">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div className="px-5 py-3 border-b flex items-center justify-between">
          <h3 className="font-semibold text-slate-900 flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-emerald-600" /> Token created
          </h3>
          <button onClick={onClose}><X className="h-5 w-5 text-slate-400" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800">
              This is the only time we&apos;ll show the full secret. Copy it now and store it somewhere safe — IFPI keeps only a hash.
            </p>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">{name}</label>
            <div className="flex gap-2">
              <code className="flex-1 px-3 py-2 bg-slate-900 text-emerald-300 font-mono text-xs rounded-lg break-all select-all" data-testid="reveal-token-value">{token}</code>
              <button onClick={copy} data-testid="reveal-copy-btn"
                className="inline-flex items-center gap-1 text-xs border border-slate-200 hover:bg-slate-50 px-3 py-1.5 rounded-lg whitespace-nowrap">
                <Copy className="h-3.5 w-3.5" /> Copy
              </button>
            </div>
          </div>
          <p className="text-[11px] text-slate-500">
            Use as a standard <code className="font-mono">Authorization: Bearer …</code> header in any HTTP client.
          </p>
        </div>
        <div className="px-5 py-3 border-t flex justify-end">
          <button onClick={onClose} className="px-3 py-1.5 text-sm bg-slate-900 text-white hover:bg-slate-800 font-semibold rounded-lg">I&apos;ve copied it</button>
        </div>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { Webhook, Plus, Trash2, Send, Eye, EyeOff, Copy, Check, AlertCircle, Activity } from 'lucide-react'
import { toast } from 'sonner'
<<<<<<< HEAD
import { useConfirm } from 'components/ConfirmDialog'
=======
>>>>>>> origin/main

interface Subscription {
  id: number
  target_url: string
  events: string[]
  description: string | null
  is_active: boolean
  secret: string
  created_at: string
  last_success_at: string | null
  last_failure_at: string | null
}

interface Delivery {
  id: number
  event_type: string
  event_id: string
  status: 'QUEUED' | 'DELIVERED' | 'FAILED' | 'DEAD_LETTER'
  status_code: number | null
  attempt_count: number
  error: string | null
  created_at: string
  delivered_at: string | null
}

const STATUS_COLORS: Record<string, string> = {
  QUEUED: 'bg-slate-100 text-slate-700',
  DELIVERED: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  FAILED: 'bg-amber-50 text-amber-700 border border-amber-200',
  DEAD_LETTER: 'bg-rose-50 text-rose-700 border border-rose-200',
}

export default function WebhooksPage() {
<<<<<<< HEAD
  const confirm = useConfirm()
=======
>>>>>>> origin/main
  const [subs, setSubs] = useState<Subscription[]>([])
  const [knownEvents, setKnownEvents] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [expandedSub, setExpandedSub] = useState<number | null>(null)
  const [deliveries, setDeliveries] = useState<Record<number, Delivery[]>>({})
  const [revealedSecrets, setRevealedSecrets] = useState<Set<number>>(new Set())
  const [testing, setTesting] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.get('/admin/webhooks')
      setSubs(r.data.items)
      setKnownEvents(r.data.known_events || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const loadDeliveries = async (subId: number) => {
    try {
      const r = await api.get(`/admin/webhooks/${subId}/deliveries`)
      setDeliveries(d => ({ ...d, [subId]: r.data.items }))
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Could not load deliveries') }
  }

  const toggleExpand = (id: number) => {
    if (expandedSub === id) { setExpandedSub(null); return }
    setExpandedSub(id); loadDeliveries(id)
  }

  const sendTest = async (id: number) => {
    setTesting(id)
    try {
      const r = await api.post(`/admin/webhooks/${id}/test`)
      if (r.data.status === 'DELIVERED') {
        toast.success(`Test ping delivered (HTTP ${r.data.status_code})`)
      } else {
        toast.error(`Test failed — ${r.data.status} ${r.data.status_code ?? ''}: ${(r.data.error || '').slice(0, 120)}`)
      }
      if (expandedSub === id) loadDeliveries(id)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Test failed')
    } finally { setTesting(null) }
  }

  const remove = async (id: number) => {
<<<<<<< HEAD
    if (!(await confirm({
      title: 'Delete webhook subscription?',
      description: 'The subscription and all delivery history will be removed. External systems relying on it will stop receiving events.',
      confirmLabel: 'Delete', variant: 'danger',
    }))) return
=======
    if (!window.confirm('Delete this webhook subscription? Deliveries will be removed too.')) return
>>>>>>> origin/main
    try {
      await api.delete(`/admin/webhooks/${id}`)
      toast.success('Subscription deleted')
      load()
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Delete failed') }
  }

  const toggleActive = async (s: Subscription) => {
    try {
      await api.put(`/admin/webhooks/${s.id}`, {
        target_url: s.target_url, events: s.events,
        description: s.description, is_active: !s.is_active,
      })
      load()
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Toggle failed') }
  }

  const toggleSecret = (id: number) => {
    setRevealedSecrets(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const copy = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Webhook className="h-6 w-6 text-indigo-600" /> Outgoing webhooks
          </h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">
            Mirror IFPI events to external systems like ERP360. Each event POST is signed with HMAC-SHA256 of the request body so receivers can verify authenticity.
          </p>
        </div>
        <button onClick={() => setShowAdd(true)} data-testid="add-webhook-btn"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">
          <Plus className="h-4 w-4" /> Add subscription
        </button>
      </div>

      {loading ? (
        <div className="text-sm text-slate-400">Loading…</div>
      ) : subs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/50 p-10 text-center">
          <Webhook className="h-10 w-10 text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-600 font-medium">No webhook subscriptions yet</p>
          <p className="text-xs text-slate-400 mt-1">Add one to mirror course completions, certificate issuances, and cohort milestones to ERP360 or any HTTPS endpoint.</p>
        </div>
      ) : (
        <div className="space-y-3" data-testid="webhooks-list">
          {subs.map(s => (
            <div key={s.id} className="rounded-xl border border-slate-200 bg-white" data-testid={`webhook-row-${s.id}`}>
              <div className="p-4 flex items-start gap-3">
                <div className={`mt-1 h-2 w-2 rounded-full flex-shrink-0 ${s.is_active ? 'bg-emerald-500 shadow-sm shadow-emerald-300' : 'bg-slate-300'}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs text-slate-800 truncate" title={s.target_url}>{s.target_url}</span>
                    {!s.is_active && <span className="text-[10px] uppercase font-semibold text-slate-400 bg-slate-100 px-2 py-0.5 rounded">Disabled</span>}
                  </div>
                  {s.description && <p className="text-xs text-slate-500 mt-1">{s.description}</p>}
                  <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                    {s.events.map(ev => (
                      <span key={ev} className="text-[10px] font-mono bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded">
                        {ev}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 mt-2 text-[10px] text-slate-400">
                    <span>Secret:</span>
                    <code className="font-mono bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">
                      {revealedSecrets.has(s.id) ? s.secret : '••••••••••••••••'}
                    </code>
                    <button onClick={() => toggleSecret(s.id)} className="text-slate-400 hover:text-slate-600" data-testid={`reveal-secret-${s.id}`}>
                      {revealedSecrets.has(s.id) ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                    </button>
                    <button onClick={() => copy(s.secret)} className="text-slate-400 hover:text-slate-600">
                      <Copy className="h-3 w-3" />
                    </button>
                    {s.last_success_at && <span className="ml-2 text-emerald-600">✓ Last delivered: {new Date(s.last_success_at).toLocaleString()}</span>}
                    {!s.last_success_at && s.last_failure_at && <span className="ml-2 text-rose-600 flex items-center gap-1"><AlertCircle className="h-3 w-3" /> Last failure: {new Date(s.last_failure_at).toLocaleString()}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <button onClick={() => sendTest(s.id)} disabled={testing === s.id}
                    data-testid={`webhook-test-${s.id}`}
                    className="inline-flex items-center gap-1.5 text-xs border border-slate-200 hover:bg-slate-50 px-2.5 py-1.5 rounded-lg disabled:opacity-40">
                    <Send className="h-3 w-3" /> {testing === s.id ? 'Pinging…' : 'Test'}
                  </button>
                  <button onClick={() => toggleExpand(s.id)}
                    data-testid={`webhook-expand-${s.id}`}
                    className="inline-flex items-center gap-1.5 text-xs border border-slate-200 hover:bg-slate-50 px-2.5 py-1.5 rounded-lg">
                    <Activity className="h-3 w-3" /> Log
                  </button>
                  <button onClick={() => toggleActive(s)}
                    className="text-xs border border-slate-200 hover:bg-slate-50 px-2.5 py-1.5 rounded-lg">
                    {s.is_active ? 'Disable' : 'Enable'}
                  </button>
                  <button onClick={() => remove(s.id)}
                    data-testid={`webhook-delete-${s.id}`}
                    className="text-rose-600 hover:bg-rose-50 p-1.5 rounded-lg">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              {expandedSub === s.id && (
                <div className="border-t border-slate-100 px-4 py-3 bg-slate-50/40" data-testid={`webhook-deliveries-${s.id}`}>
                  <h3 className="text-xs font-semibold text-slate-600 mb-2 uppercase tracking-wide">Recent deliveries</h3>
                  {!deliveries[s.id] ? (
                    <div className="text-xs text-slate-400">Loading…</div>
                  ) : deliveries[s.id].length === 0 ? (
                    <div className="text-xs text-slate-400">No deliveries yet — hit "Test" to fire a ping.</div>
                  ) : (
                    <div className="space-y-1.5">
                      {deliveries[s.id].map(d => (
                        <div key={d.id} className="flex items-center gap-3 text-xs">
                          <span className={`font-semibold px-2 py-0.5 rounded ${STATUS_COLORS[d.status] || 'bg-slate-100 text-slate-700'}`}>
                            {d.status}{d.status_code ? ` ${d.status_code}` : ''}
                          </span>
                          <span className="font-mono text-slate-700">{d.event_type}</span>
                          <span className="text-slate-400">attempt {d.attempt_count}</span>
                          <span className="text-slate-400 ml-auto">{new Date(d.created_at).toLocaleString()}</span>
                          {d.error && <span className="text-rose-600 truncate max-w-md" title={d.error}>{d.error}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showAdd && (
        <AddSubscriptionModal knownEvents={knownEvents}
          onClose={() => setShowAdd(false)}
          onSaved={() => { setShowAdd(false); load() }} />
      )}
    </div>
  )
}


function AddSubscriptionModal({ knownEvents, onClose, onSaved }:
  { knownEvents: string[]; onClose: () => void; onSaved: () => void }) {
  const [url, setUrl] = useState('')
  const [description, setDescription] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set(['*']))
  const [secret, setSecret] = useState('')
  const [saving, setSaving] = useState(false)

  const toggle = (ev: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (ev === '*') {
        return next.has('*') ? new Set() : new Set(['*'])
      }
      next.delete('*')
      if (next.has(ev)) next.delete(ev); else next.add(ev)
      return next
    })
  }

  const submit = async () => {
    if (!url.trim()) { toast.error('Target URL is required'); return }
    if (selected.size === 0) { toast.error('Pick at least one event'); return }
    setSaving(true)
    try {
      await api.post('/admin/webhooks', {
        target_url: url.trim(),
        events: Array.from(selected),
        description: description.trim() || null,
        secret: secret.trim() || undefined,
        is_active: true,
      })
      toast.success('Subscription created')
      onSaved()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Create failed')
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose} data-testid="add-webhook-modal">
      <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-slate-900 mb-4">Add webhook subscription</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Target URL *</label>
            <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://erp360.example.com/api/webhooks/ifpi"
              data-testid="webhook-url"
              className="w-full font-mono text-xs px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/30" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Events</label>
            <div className="flex flex-wrap gap-1.5">
              {['*', ...knownEvents].map(ev => (
                <button key={ev} type="button" onClick={() => toggle(ev)}
                  data-testid={`event-toggle-${ev}`}
                  className={`text-[11px] font-mono px-2.5 py-1 rounded-full border ${selected.has(ev) ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300'}`}>
                  {ev}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-slate-400 mt-1.5">Pick `*` for all current and future events.</p>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Description (optional)</label>
            <input value={description} onChange={e => setDescription(e.target.value)} placeholder="e.g. ERP360 production mirror"
              className="w-full text-sm px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/30" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">HMAC secret (auto-generated if blank)</label>
            <input value={secret} onChange={e => setSecret(e.target.value)} placeholder="Leave empty to generate a secure random value"
              className="w-full font-mono text-xs px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/30" />
            <p className="text-[10px] text-slate-400 mt-1.5">Share this secret with the receiver so they can verify HMAC-SHA256(secret, body).</p>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancel</button>
          <button onClick={submit} disabled={saving} data-testid="webhook-save"
            className="inline-flex items-center gap-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2 rounded-lg">
            {saving ? 'Saving…' : <><Check className="h-4 w-4" /> Create</>}
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * Iter 30s — Affiliate / Referral admin UI.
 *
 * List codes, create new codes, view referrals + earnings snapshot.
 * Each code has a shareable URL — clicking Copy puts the full signup
 * URL in the clipboard.
 */
import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { Users, Plus, Copy, Check, DollarSign, ToggleRight } from 'lucide-react'
import { toast } from 'sonner'

type Code = {
  id: number; code: string; reward_bps: number; reward_pct: number
  cap_credits_cents: number | null; is_active: boolean
  expires_at: string | null; note: string | null; created_at: string
}
type Referral = {
  id: number; code: string; referred_org_id: number
  referred_org_name: string; signed_up_at: string; status: string
  credit_cents: number | null; credited_at: string | null
}
type Earnings = {
  total_credited_cents: number
  total_pending_cents: number
  by_status: Record<string, { count: number; cents: number }>
}

const fmt$ = (cents: number) => `$${(cents / 100).toFixed(2)}`

export default function AffiliatePage() {
  const [codes, setCodes] = useState<Code[]>([])
  const [refs, setRefs] = useState<Referral[]>([])
  const [earn, setEarn] = useState<Earnings | null>(null)
  const [reward, setReward] = useState(10)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [copiedId, setCopiedId] = useState<number | null>(null)

  const load = async () => {
    const [c, r, e] = await Promise.all([
      api.get('/admin/affiliate/codes'),
      api.get('/admin/affiliate/referrals'),
      api.get('/admin/affiliate/earnings'),
    ])
    setCodes(c.data.items); setRefs(r.data.items); setEarn(e.data)
  }
  useEffect(() => { load() }, [])

  const create = async () => {
    setBusy(true)
    try {
      await api.post('/admin/affiliate/codes', {
        reward_bps: Math.round(reward * 100),
        note: note.trim() || null,
      })
      setNote('')
      await load()
      toast.success('Referral code created')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Create failed')
    } finally { setBusy(false) }
  }

  const toggle = async (c: Code) => {
    try {
      await api.patch(`/admin/affiliate/codes/${c.id}`, { is_active: !c.is_active })
      await load()
    } catch { toast.error('Update failed') }
  }

  const copyLink = (code: string, id: number) => {
    const url = `${window.location.origin}/register?ref=${code}`
    navigator.clipboard.writeText(url)
    setCopiedId(id); setTimeout(() => setCopiedId(null), 1500)
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6" data-testid="affiliate-page">
      <header className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-lg bg-gradient-to-br from-fuchsia-600 to-indigo-600 flex items-center justify-center">
          <Users className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Affiliate program</h1>
          <p className="text-sm text-slate-500">
            Earn credit when new organisations sign up using your referral link.
          </p>
        </div>
      </header>

      {earn && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
            <p className="text-xs uppercase font-semibold text-emerald-700">Total credited</p>
            <p className="text-3xl font-bold text-emerald-900 mt-1">{fmt$(earn.total_credited_cents)}</p>
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <p className="text-xs uppercase font-semibold text-amber-700">Pending</p>
            <p className="text-3xl font-bold text-amber-900 mt-1">{fmt$(earn.total_pending_cents)}</p>
          </div>
        </div>
      )}

      <section className="bg-white border border-slate-200 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-slate-800 mb-3">Create a new code</h2>
        <div className="grid gap-3 sm:grid-cols-[6rem_1fr_auto]">
          <div>
            <label className="block text-[10px] uppercase font-semibold text-slate-500 mb-1">Reward %</label>
            <input type="number" min={1} max={50} value={reward}
                   onChange={e => setReward(Math.max(1, Math.min(50, parseFloat(e.target.value) || 0)))}
                   data-testid="affiliate-reward-input"
                   className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-[10px] uppercase font-semibold text-slate-500 mb-1">Note (optional)</label>
            <input value={note} onChange={e => setNote(e.target.value)}
                   placeholder="e.g. Partnership X"
                   data-testid="affiliate-note-input"
                   className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          </div>
          <button onClick={create} disabled={busy}
                  data-testid="affiliate-create-btn"
                  className="mt-5 inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-sm font-semibold px-4 py-2 rounded-lg h-fit">
            <Plus className="h-4 w-4" /> Create
          </button>
        </div>
      </section>

      <section className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-800">Your codes ({codes.length})</h2>
        </div>
        {codes.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-400" data-testid="affiliate-empty">
            No codes yet — create one above to start earning referral credit.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100" data-testid="affiliate-codes">
            {codes.map(c => (
              <li key={c.id} className="flex items-center gap-4 px-5 py-3" data-testid={`affiliate-code-${c.id}`}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <code className="text-lg font-mono font-bold text-indigo-700 bg-indigo-50 border border-indigo-100 rounded px-2 py-0.5">
                      {c.code}
                    </code>
                    <span className="text-xs font-semibold text-emerald-700">
                      {c.reward_pct.toFixed(1)}% reward
                    </span>
                    {!c.is_active && (
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-200 text-slate-500 uppercase">Off</span>
                    )}
                  </div>
                  {c.note && <p className="text-xs text-slate-500 mt-0.5">{c.note}</p>}
                </div>
                <button onClick={() => copyLink(c.code, c.id)}
                        data-testid={`affiliate-copy-${c.id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold border border-slate-200 hover:border-indigo-300 hover:text-indigo-700 rounded-lg px-3 py-1.5">
                  {copiedId === c.id ? <><Check className="h-3 w-3" /> Copied</> : <><Copy className="h-3 w-3" /> Copy link</>}
                </button>
                <button onClick={() => toggle(c)}
                        data-testid={`affiliate-toggle-${c.id}`}
                        title={c.is_active ? 'Deactivate' : 'Activate'}
                        className={`p-2 rounded-lg ${c.is_active ? 'text-indigo-600 hover:bg-indigo-50' : 'text-slate-400 hover:bg-slate-100'}`}>
                  <ToggleRight className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-800">Recent referrals ({refs.length})</h2>
        </div>
        {refs.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-400">No referrals yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {refs.map(r => (
              <li key={r.id} className="flex items-center gap-3 px-5 py-3">
                <DollarSign className={`h-4 w-4 ${r.status === 'CREDITED' ? 'text-emerald-500' : 'text-slate-300'}`} />
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-800">{r.referred_org_name}</p>
                  <p className="text-xs text-slate-500">
                    via <span className="font-mono">{r.code}</span> · {new Date(r.signed_up_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="text-right">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                    r.status === 'CREDITED' ? 'bg-emerald-100 text-emerald-700'
                      : r.status === 'REJECTED' ? 'bg-rose-100 text-rose-700'
                      : 'bg-amber-100 text-amber-700'}`}>
                    {r.status}
                  </span>
                  {r.credit_cents && <p className="text-xs font-semibold text-slate-700 mt-0.5">{fmt$(r.credit_cents)}</p>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

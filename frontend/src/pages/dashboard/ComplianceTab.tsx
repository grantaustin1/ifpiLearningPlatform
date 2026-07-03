/**
 * Iter 30l — Admin UI for T&Cs versioning, kiosk config, feature flags.
 *
 * One tab, three sections. Kept in a single component for cohesion —
 * these settings are all under "Compliance & Access" conceptually.
 */
import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { ScrollText, Lock, ToggleRight, Plus, Check, X } from 'lucide-react'
import { toast } from 'sonner'

type Version = { id: number; version: string; title: string; body_markdown: string; is_current: boolean; published_at: string }
type Flag = { key: string; default: boolean; description: string }
type KioskState = { enabled: boolean; idle_timeout_seconds: number; has_pin: boolean }

export function ComplianceTab() {
  // ── T&Cs ──
  const [versions, setVersions] = useState<Version[]>([])
  const [newVersion, setNewVersion] = useState('')
  const [newTitle, setNewTitle] = useState('Terms of Service')
  const [newBody, setNewBody] = useState('')
  // ── Kiosk ──
  const [kiosk, setKiosk] = useState<KioskState>({ enabled: false, idle_timeout_seconds: 300, has_pin: false })
  const [newPin, setNewPin] = useState('')
  // ── Flags ──
  const [flags, setFlags] = useState<Record<string, boolean>>({})
  const [known, setKnown] = useState<Flag[]>([])
  const [busy, setBusy] = useState(false)

  const load = async () => {
    const [t, k, f] = await Promise.all([
      api.get('/admin/terms'),
      api.get('/kiosk/settings'),
      api.get('/feature-flags'),
    ])
    setVersions(t.data.items)
    setKiosk(k.data)
    setFlags(f.data.flags)
    setKnown(f.data.known_flags)
  }
  useEffect(() => { load() }, [])

  const publishTerms = async () => {
    if (!newVersion || !newBody) return toast.error('Version + body are required')
    setBusy(true)
    try {
      await api.post('/admin/terms', { version: newVersion, title: newTitle, body_markdown: newBody })
      setNewVersion(''); setNewBody(''); setNewTitle('Terms of Service')
      await load()
      toast.success(`Published v${newVersion}`)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Publish failed')
    } finally { setBusy(false) }
  }

  const saveKiosk = async () => {
    setBusy(true)
    try {
      const body: any = { enabled: kiosk.enabled, idle_timeout_seconds: kiosk.idle_timeout_seconds }
      if (newPin) body.unlock_pin = newPin
      await api.put('/admin/kiosk/settings', body)
      setNewPin('')
      await load()
      toast.success('Kiosk settings saved')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Save failed')
    } finally { setBusy(false) }
  }

  const toggleFlag = async (key: string, next: boolean) => {
    try {
      await api.put(`/admin/feature-flags/${key}`, { enabled: next })
      setFlags(prev => ({ ...prev, [key]: next }))
      toast.success(`${key} ${next ? 'enabled' : 'disabled'}`)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Toggle failed')
    }
  }

  return (
    <div className="space-y-8 max-w-4xl" data-testid="compliance-tab">
      {/* ── T&Cs ─────────────────────────────────────────────────── */}
      <section className="bg-white border border-slate-200 rounded-xl">
        <header className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
          <ScrollText className="h-5 w-5 text-indigo-600" />
          <div className="flex-1">
            <h2 className="text-base font-semibold text-slate-900">Terms & Conditions</h2>
            <p className="text-xs text-slate-500">Publishing a new version requires all users to re-accept.</p>
          </div>
        </header>
        <div className="p-6 space-y-4">
          <div className="grid gap-3 md:grid-cols-[8rem_1fr]">
            <input value={newVersion} onChange={e => setNewVersion(e.target.value)}
              placeholder="e.g. 2.1"
              data-testid="terms-new-version"
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            <input value={newTitle} onChange={e => setNewTitle(e.target.value)}
              placeholder="Title"
              data-testid="terms-new-title"
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
          <textarea value={newBody} onChange={e => setNewBody(e.target.value)}
            rows={5} placeholder="Markdown body — this is what learners see in the acceptance modal"
            data-testid="terms-new-body"
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          <button onClick={publishTerms} disabled={busy || !newVersion || !newBody}
            data-testid="terms-publish-btn"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-40">
            <Plus className="h-4 w-4" /> Publish version
          </button>

          <div className="mt-6">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Published versions</h3>
            {versions.length === 0 ? (
              <p className="text-sm text-slate-400 italic">No versions published yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100 border border-slate-100 rounded-lg">
                {versions.map(v => (
                  <li key={v.id} className="px-3 py-2 flex items-center gap-2 text-sm" data-testid={`terms-version-${v.id}`}>
                    <span className="font-mono font-semibold text-slate-700">v{v.version}</span>
                    <span className="text-slate-500">·</span>
                    <span className="text-slate-600 flex-1 truncate">{v.title}</span>
                    {v.is_current && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200">CURRENT</span>
                    )}
                    <span className="text-xs text-slate-400">{new Date(v.published_at).toLocaleDateString()}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      {/* ── Kiosk ────────────────────────────────────────────────── */}
      <section className="bg-white border border-slate-200 rounded-xl">
        <header className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
          <Lock className="h-5 w-5 text-indigo-600" />
          <div className="flex-1">
            <h2 className="text-base font-semibold text-slate-900">Kiosk mode</h2>
            <p className="text-xs text-slate-500">Auto-lock shared devices after inactivity. Unlock with PIN or password.</p>
          </div>
        </header>
        <div className="p-6 space-y-4">
          <label className="flex items-center gap-3">
            <input type="checkbox" checked={kiosk.enabled}
              onChange={e => setKiosk({ ...kiosk, enabled: e.target.checked })}
              data-testid="kiosk-enabled-toggle"
              className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
            <span className="text-sm text-slate-700 font-medium">Enable kiosk mode for this organisation</span>
          </label>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Idle timeout (seconds)</label>
              <input type="number" min={30} max={3600} value={kiosk.idle_timeout_seconds}
                onChange={e => setKiosk({ ...kiosk, idle_timeout_seconds: parseInt(e.target.value) || 0 })}
                data-testid="kiosk-timeout-input"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Unlock PIN {kiosk.has_pin && <span className="text-emerald-600 text-[10px]">(currently set)</span>}
              </label>
              <input type="password" inputMode="numeric" value={newPin}
                onChange={e => setNewPin(e.target.value)}
                placeholder={kiosk.has_pin ? 'Leave blank to keep existing' : '4-10 digits'}
                data-testid="kiosk-pin-input-admin"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
          </div>
          <button onClick={saveKiosk} disabled={busy}
            data-testid="kiosk-save-btn"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-40">
            <Check className="h-4 w-4" /> Save kiosk settings
          </button>
        </div>
      </section>

      {/* ── Feature flags ────────────────────────────────────────── */}
      <section className="bg-white border border-slate-200 rounded-xl">
        <header className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
          <ToggleRight className="h-5 w-5 text-indigo-600" />
          <div className="flex-1">
            <h2 className="text-base font-semibold text-slate-900">Feature modules</h2>
            <p className="text-xs text-slate-500">Turn app modules on or off for this organisation.</p>
          </div>
        </header>
        <ul className="divide-y divide-slate-100">
          {known.map(f => (
            <li key={f.key} className="flex items-center gap-4 px-6 py-3" data-testid={`flag-row-${f.key}`}>
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-800 font-mono">{f.key}</p>
                <p className="text-xs text-slate-500">{f.description}</p>
              </div>
              <button
                onClick={() => toggleFlag(f.key, !flags[f.key])}
                data-testid={`flag-toggle-${f.key}`}
                className={`inline-flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg border ${
                  flags[f.key]
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                    : 'bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200'}`}>
                {flags[f.key] ? <><Check className="h-3 w-3" /> On</> : <><X className="h-3 w-3" /> Off</>}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

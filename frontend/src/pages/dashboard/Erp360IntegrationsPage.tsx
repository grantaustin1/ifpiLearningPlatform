import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Link2, ShieldCheck, ShieldOff, Save, Info } from 'lucide-react'
import { toast } from 'sonner'

interface Integration {
  organization_id: number
  organization_slug: string
  connected: boolean
  sso_enabled: boolean
  org_slug: string | null
  billing_mode: string | null
  raw: Record<string, unknown>
}

const BILLING_MODES = [
  { value: '', label: '— unset —' },
  { value: 'erp360', label: 'ERP360 (lite-billing webhook)' },
  { value: 'native_stripe', label: 'Native Stripe (P1 future)' },
]

export default function Erp360IntegrationsPage() {
  const qc = useQueryClient()
  const [orgId] = useState<number>(1)  // scoped-admin sees their own org
  const [draft, setDraft] = useState<Partial<Integration> | null>(null)

  const { data, isLoading } = useQuery<Integration>({
    queryKey: ['erp360-integration', orgId],
    queryFn: async () =>
      (await api.get(`/admin/organizations/${orgId}/integrations/erp360`)).data,
    // Snapshot into local draft on first load
    onSuccess: (r) => { if (!draft) setDraft(r) },
  } as any)

  const saveMut = useMutation({
    mutationFn: async (patch: Partial<Integration>) =>
      (await api.patch(`/admin/organizations/${orgId}/integrations/erp360`, patch)).data,
    onSuccess: () => {
      toast.success('ERP360 integration updated')
      qc.invalidateQueries({ queryKey: ['erp360-integration', orgId] })
    },
    onError: (e: any) =>
      toast.error(e?.response?.data?.error?.message
        || e?.response?.data?.detail
        || 'Update failed'),
  })

  const view: Integration | null = draft as Integration | null || data || null

  const set = <K extends keyof Integration>(k: K, v: Integration[K]) => {
    setDraft(prev => ({ ...(prev || data || {}), [k]: v }))
  }

  const submit = () => {
    if (!view) return
    saveMut.mutate({
      connected: view.connected,
      sso_enabled: view.sso_enabled,
      org_slug: view.org_slug ?? '',
      billing_mode: view.billing_mode ?? '',
    })
  }

  if (isLoading || !view) {
    return <div className="text-sm text-slate-500">Loading integration…</div>
  }

  return (
    <div className="max-w-2xl space-y-6" data-testid="erp360-integrations-page">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
          <Link2 className="h-6 w-6 text-indigo-600" />
          ERP360 Integration
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Per-org connection state for the ERP360 SSO bridge and lite-billing
          webhook. Set <code className="text-xs bg-slate-100 px-1 rounded">sso_enabled=true</code> and
          match <code className="text-xs bg-slate-100 px-1 rounded">org_slug</code> to what ERP360
          sends in its JWT claim to enable production SSO for this
          organization.
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5">
        {/* Connected toggle */}
        <label className="flex items-start gap-3 cursor-pointer"
          data-testid="erp360-connected-toggle">
          <input type="checkbox"
            checked={view.connected}
            onChange={e => set('connected', e.target.checked)}
            className="mt-1 h-4 w-4 accent-indigo-600" />
          <div>
            <div className="text-sm font-medium text-slate-900">
              Connected to ERP360
            </div>
            <div className="text-xs text-slate-500">
              Master switch. Turn on once ERP360 has provisioned this
              org's shared secrets on their side.
            </div>
          </div>
        </label>

        {/* SSO toggle */}
        <label className="flex items-start gap-3 cursor-pointer"
          data-testid="erp360-sso-toggle">
          <input type="checkbox"
            checked={view.sso_enabled}
            onChange={e => set('sso_enabled', e.target.checked)}
            className="mt-1 h-4 w-4 accent-indigo-600" />
          <div>
            <div className="text-sm font-medium text-slate-900 flex items-center gap-1">
              {view.sso_enabled
                ? <ShieldCheck className="h-4 w-4 text-emerald-600" />
                : <ShieldOff className="h-4 w-4 text-slate-400" />}
              SSO enabled
            </div>
            <div className="text-xs text-slate-500">
              When on, users from this org can sign in via the ERP360
              tile. When off, they must use email + password. Learners
              already provisioned via SSO are not affected.
            </div>
          </div>
        </label>

        {/* ERP360-side org slug */}
        <div>
          <label className="block text-sm font-medium text-slate-900 mb-1">
            ERP360-side org slug
          </label>
          <input type="text"
            value={view.org_slug ?? ''}
            onChange={e => set('org_slug', e.target.value)}
            placeholder="e.g. 'my-institute'"
            data-testid="erp360-org-slug-input"
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500" />
          <p className="text-xs text-slate-500 mt-1">
            Value ERP360 places in the JWT claim <code>org_slug</code>. Leave blank in
            single-tenant preview to auto-match by native slug. Empty
            string clears the mapping.
          </p>
        </div>

        {/* Billing mode */}
        <div>
          <label className="block text-sm font-medium text-slate-900 mb-1">
            Billing mode
          </label>
          <select value={view.billing_mode ?? ''}
            onChange={e => set('billing_mode', e.target.value)}
            data-testid="erp360-billing-mode-select"
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500">
            {BILLING_MODES.map(m => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
          <p className="text-xs text-slate-500 mt-1">
            Which payment webhook writes entitlements for this org.
            Enrollment code is decoupled from this — flipping it is
            safe at any time (existing entitlements are preserved).
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-3">
        <button onClick={submit} disabled={saveMut.isPending}
          data-testid="erp360-save-btn"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition">
          <Save className="h-4 w-4" />
          {saveMut.isPending ? 'Saving…' : 'Save changes'}
        </button>
      </div>

      {/* Raw state (debug) */}
      <details className="bg-slate-50 rounded-lg p-4">
        <summary className="text-xs font-medium text-slate-600 cursor-pointer flex items-center gap-2">
          <Info className="h-3 w-3" /> Raw integration JSON (advanced)
        </summary>
        <pre className="mt-2 text-xs text-slate-700 whitespace-pre-wrap"
          data-testid="erp360-raw-json">
{JSON.stringify(view.raw, null, 2)}
        </pre>
      </details>
    </div>
  )
}

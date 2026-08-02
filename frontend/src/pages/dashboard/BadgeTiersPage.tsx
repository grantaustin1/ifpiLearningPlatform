import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Award, GripVertical, Plus, Trash2, X, Edit, Eye, EyeOff } from 'lucide-react'
import { toast } from 'sonner'
import { SortableList } from 'components/SortableList'
<<<<<<< HEAD
import { useConfirm } from 'components/ConfirmDialog'
=======
>>>>>>> origin/main

interface Tier {
  id: number; slug: string; label: string; emoji: string
  description?: string | null; threshold_xp: number
  order_index: number; is_active: boolean
}

export default function BadgeTiersPage() {
  const qc = useQueryClient()
<<<<<<< HEAD
  const confirm = useConfirm()
=======
>>>>>>> origin/main
  const [editing, setEditing] = useState<Tier | null>(null)
  const [creating, setCreating] = useState(false)

  const { data: tiers = [], isLoading } = useQuery<Tier[]>({
    queryKey: ['badge-tiers'],
    queryFn: async () => (await api.get('/badge-tiers')).data,
  })

  const reorderMut = useMutation({
    mutationFn: async (ids: number[]) => (await api.patch('/badge-tiers/reorder', { tier_ids: ids })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['badge-tiers'] }),
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Reorder failed'),
  })

  const delMut = useMutation({
    mutationFn: async (id: number) => (await api.delete(`/badge-tiers/${id}`)).data,
    onSuccess: () => { toast.success('Tier deleted'); qc.invalidateQueries({ queryKey: ['badge-tiers'] }) },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Delete failed'),
  })

  return (
    <div className="space-y-6" data-testid="badge-tiers-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Badge tiers</h1>
          <p className="text-sm text-slate-500">Configure the badge ladder your learners climb. Drag to reorder. Slugs are referenced by the gamification engine and shouldn't change after launch.</p>
        </div>
        <button onClick={() => setCreating(true)} data-testid="new-tier-btn"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
          <Plus className="h-4 w-4" /> New tier
        </button>
      </div>

      {isLoading ? (
        <div className="text-sm text-slate-500">Loading…</div>
      ) : tiers.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-2xl">
          <Award className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-500">No badge tiers yet. Click "New tier" to seed one.</p>
        </div>
      ) : (
        <div className="max-w-3xl">
          <SortableList items={tiers} onReorder={(ids) => reorderMut.mutate(ids as number[])}>
            {(t: Tier, listeners: any) => (
              <div className={`bg-white rounded-xl border shadow-sm flex items-center gap-3 p-4 mb-2 ${t.is_active ? 'border-slate-200' : 'border-slate-200 opacity-60'}`}
                   data-testid={`tier-row-${t.id}`}>
                <button {...listeners} className="text-slate-400 hover:text-slate-600 cursor-grab" aria-label="drag"><GripVertical className="h-5 w-5" /></button>
                <span className="text-2xl">{t.emoji}</span>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-900 truncate">{t.label}</p>
                  <p className="text-xs text-slate-500 font-mono truncate">{t.slug}</p>
                  {t.description && <p className="text-xs text-slate-500 mt-1 line-clamp-1">{t.description}</p>}
                </div>
                <div className="text-right pr-3">
                  <p className="text-xs text-slate-400">Threshold</p>
                  <p className="text-sm font-semibold text-slate-700">{t.threshold_xp} XP</p>
                </div>
                {!t.is_active && <span className="text-[10px] uppercase font-medium text-slate-400 px-2">Disabled</span>}
                <button onClick={() => setEditing(t)} data-testid={`tier-edit-${t.id}`}
                        className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-md">
                  <Edit className="h-4 w-4" />
                </button>
<<<<<<< HEAD
                <button onClick={async () => {
                  if (await confirm({
                    title: `Delete tier "${t.label}"?`,
                    description: 'Users currently at this tier will be re-ranked to the nearest remaining tier.',
                    confirmLabel: 'Delete', variant: 'danger',
                  })) delMut.mutate(t.id)
                }} data-testid={`tier-delete-${t.id}`}
=======
                <button onClick={() => { if (window.confirm(`Delete "${t.label}"?`)) delMut.mutate(t.id) }} data-testid={`tier-delete-${t.id}`}
>>>>>>> origin/main
                        className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-md">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            )}
          </SortableList>
        </div>
      )}

      {(creating || editing) && (
        <TierModal
          tier={editing}
          onClose={() => { setEditing(null); setCreating(false) }}
          onSaved={() => { setEditing(null); setCreating(false); qc.invalidateQueries({ queryKey: ['badge-tiers'] }) }}
        />
      )}
    </div>
  )
}

function TierModal({ tier, onClose, onSaved }: { tier: Tier | null, onClose: () => void, onSaved: () => void }) {
  const [form, setForm] = useState({
    slug: tier?.slug || '',
    label: tier?.label || '',
    emoji: tier?.emoji || '🏅',
    description: tier?.description || '',
    threshold_xp: tier?.threshold_xp || 0,
    is_active: tier?.is_active ?? true,
  })
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    setSaving(true)
    try {
      if (tier) {
        await api.patch(`/badge-tiers/${tier.id}`, {
          label: form.label, emoji: form.emoji, description: form.description,
          threshold_xp: Number(form.threshold_xp) || 0, is_active: form.is_active,
        })
        toast.success('Tier updated')
      } else {
        await api.post('/badge-tiers', form)
        toast.success('Tier created')
      }
      onSaved()
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Save failed') }
    finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div onClick={e => e.stopPropagation()} className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6" data-testid="tier-modal">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">{tier ? 'Edit tier' : 'New tier'}</h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600"><X className="h-5 w-5" /></button>
        </div>
        <div className="space-y-3">
          {!tier && (
            <Field label="Slug" help="Uppercase A-Z and underscores. Referenced by the gamification engine.">
              <input value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value }))}
                     data-testid="tier-slug" placeholder="LEGENDARY_LEARNER"
                     className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono" />
            </Field>
          )}
          <div className="grid grid-cols-[80px_1fr] gap-3">
            <Field label="Emoji">
              <input value={form.emoji} onChange={e => setForm(f => ({ ...f, emoji: e.target.value }))}
                     data-testid="tier-emoji" maxLength={4}
                     className="w-full px-3 py-2 border border-slate-200 rounded-lg text-2xl text-center" />
            </Field>
            <Field label="Label">
              <input value={form.label} onChange={e => setForm(f => ({ ...f, label: e.target.value }))}
                     data-testid="tier-label"
                     className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" />
            </Field>
          </div>
          <Field label="Description">
            <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                      data-testid="tier-desc" rows={2}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" />
          </Field>
          <Field label="Threshold XP" help="Informational — shown on the public ladder. Award triggers live in code.">
            <input type="number" value={form.threshold_xp} onChange={e => setForm(f => ({ ...f, threshold_xp: Number(e.target.value) }))}
                   data-testid="tier-threshold"
                   className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" />
          </Field>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={form.is_active} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))}
                   data-testid="tier-active" className="rounded" />
            {form.is_active ? <Eye className="h-4 w-4 text-emerald-600" /> : <EyeOff className="h-4 w-4 text-slate-400" />}
            Active (eligible for award)
          </label>
        </div>
        <div className="flex gap-2 justify-end mt-5">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 rounded-lg">Cancel</button>
          <button onClick={submit} disabled={saving || !form.label || (!tier && !form.slug)}
                  data-testid="tier-save"
                  className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white rounded-lg font-medium">
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, help, children }: { label: string, help?: string, children: any }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-500 mb-1">{label}</label>
      {children}
      {help && <p className="text-[11px] text-slate-400 mt-1">{help}</p>}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { toast } from 'sonner'
import { Bell, Flame, Save } from 'lucide-react'
import { useAuth } from 'contexts/AuthContext'

/**
 * Iter 31 — Dedicated user Preferences page.
 *
 * A self-service surface for per-user notification & display
 * preferences. Backed by the /api/gamification/preferences endpoint.
 * Sits under /preferences (available to every authenticated user).
 */
interface Prefs {
  streak_digest_enabled: boolean
}

export default function PreferencesPage() {
  const { user } = useAuth()
  const [prefs, setPrefs] = useState<Prefs | null>(null)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/gamification/preferences')
      .then(r => setPrefs(r.data))
      .catch(() => toast.error('Failed to load preferences'))
      .finally(() => setLoading(false))
  }, [])

  const save = async () => {
    if (!prefs) return
    setSaving(true)
    try {
      const r = await api.patch('/gamification/preferences', prefs)
      setPrefs(r.data)
      toast.success('Preferences saved')
    } catch {
      toast.error('Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading || !prefs) {
    return (
      <div className="p-8" data-testid="preferences-page-loading">
        <p className="text-slate-400 text-sm">Loading preferences…</p>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-3xl" data-testid="preferences-page">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 font-display">Preferences</h1>
        <p className="text-slate-500 mt-1">
                Manage how {user?.name || 'you'} receive notifications &amp; digests.
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
          <Bell className="h-4 w-4 text-slate-500" />
          <h2 className="font-semibold text-slate-900">Notifications</h2>
        </div>

        <div className="p-6 space-y-4">
          <label
            className="flex items-start justify-between gap-4 cursor-pointer group"
            data-testid="streak-digest-toggle-row"
          >
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Flame className="h-4 w-4 text-orange-500" />
                <span className="font-medium text-slate-900">Weekly streak digest</span>
              </div>
              <p className="text-sm text-slate-500">
                Every Monday morning we send admins a recap of the top learning
                streaks in the organisation. Turn this off if you&apos;d rather not
                receive it.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setPrefs({ ...prefs, streak_digest_enabled: !prefs.streak_digest_enabled })}
              data-testid="streak-digest-toggle"
              aria-pressed={prefs.streak_digest_enabled}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
                prefs.streak_digest_enabled ? 'bg-indigo-600' : 'bg-slate-300'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  prefs.streak_digest_enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </label>
        </div>

        <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 rounded-b-2xl flex justify-end">
          <button
            onClick={save}
            disabled={saving}
            data-testid="save-preferences-btn"
            className="inline-flex items-center gap-1.5 text-sm bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white px-4 py-2 rounded-lg font-semibold"
          >
            <Save className="h-4 w-4" /> {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </div>
    </div>
  )
}

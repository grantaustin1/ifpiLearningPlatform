import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { toast } from 'sonner'
import { Bell, Flame, Save, Download, Trash2, ShieldAlert, Mail } from 'lucide-react'
import { useAuth } from 'contexts/AuthContext'
import { useConfirm } from 'components/ConfirmDialog'
import { usePrompt } from 'components/PromptDialog'

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
  const { user, logout } = useAuth()
<<<<<<< HEAD
  const confirm = useConfirm()
=======
  const { confirm, ConfirmDialog } = useConfirm()
>>>>>>> origin/main
  const prompt = usePrompt()
  const [prefs, setPrefs] = useState<Prefs | null>(null)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<'export' | 'delete' | 'resend' | null>(null)

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

      {/* Iter 33 — Email verification section */}
      {!user?.email_verified && (
        <div className="mt-6 bg-white border border-amber-200 rounded-2xl overflow-hidden"
             data-testid="email-verification-card">
          <div className="px-6 py-4 border-b border-amber-100 flex items-center gap-2 bg-amber-50">
            <Mail className="h-4 w-4 text-amber-700" />
            <h2 className="font-semibold text-amber-900">Verify your email</h2>
          </div>
          <div className="p-6 flex items-start justify-between gap-4">
            <p className="text-sm text-slate-600 flex-1">
              We sent a verification link to <strong>{user?.email}</strong>.
              Confirm your address to unlock instructor role, marketplace
              publishing, and certificate issuance for others.
            </p>
            <button
              onClick={async () => {
                setBusy('resend')
                try {
                  await api.post('/auth/resend-verification')
                  toast.success('Verification email queued — check your inbox.')
                } catch (e: any) {
                  toast.error(e?.response?.data?.detail || 'Resend failed')
                } finally { setBusy(null) }
              }}
              disabled={busy === 'resend'}
              data-testid="resend-verification-btn"
              className="shrink-0 text-sm bg-amber-600 hover:bg-amber-700 disabled:bg-slate-300 text-white font-semibold px-4 py-2 rounded-lg"
            >
              {busy === 'resend' ? 'Sending…' : 'Resend link'}
            </button>
          </div>
        </div>
      )}

      {/* Iter 33 — GDPR data rights section */}
      <div className="mt-6 bg-white border border-slate-200 rounded-2xl overflow-hidden"
           data-testid="gdpr-section">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-slate-500" />
          <h2 className="font-semibold text-slate-900">Your data &amp; privacy</h2>
        </div>
        <div className="divide-y divide-slate-100">
          <div className="p-6 flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Download className="h-4 w-4 text-slate-500" />
                <span className="font-medium text-slate-900">Export my data</span>
              </div>
              <p className="text-sm text-slate-500">
                Download a JSON file with every piece of personal data we hold
                about you (GDPR right to portability).
              </p>
            </div>
            <button
              onClick={async () => {
                setBusy('export')
                try {
                  const r = await api.get('/auth/me/export')
                  const blob = new Blob([JSON.stringify(r.data, null, 2)],
                                        { type: 'application/json' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `ifpi-data-export-${new Date().toISOString().slice(0, 10)}.json`
                  a.click()
                  URL.revokeObjectURL(url)
                  toast.success('Export downloaded')
                } catch (e: any) {
                  toast.error(e?.response?.data?.detail || 'Export failed')
                } finally { setBusy(null) }
              }}
              disabled={busy === 'export'}
              data-testid="export-data-btn"
              className="shrink-0 text-sm bg-slate-100 hover:bg-slate-200 disabled:bg-slate-50 text-slate-700 font-semibold px-4 py-2 rounded-lg"
            >
              {busy === 'export' ? 'Preparing…' : 'Download'}
            </button>
          </div>
          <div className="p-6 flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Trash2 className="h-4 w-4 text-red-500" />
                <span className="font-medium text-slate-900">Delete my account</span>
              </div>
              <p className="text-sm text-slate-500">
                Permanently erase your account. We&apos;ll email you a 6-digit
                code — enter it in the confirmation dialog to complete the
                deletion. Certificates you&apos;ve earned remain valid but
                are anonymised.
              </p>
            </div>
            <button
              onClick={async () => {
                if (!(await confirm({
                  title: 'Delete your account?',
                  description: 'This will send a confirmation code to your email. Enter the code to complete the deletion. Cannot be undone.',
                  confirmLabel: 'Send code',
                  variant: 'danger',
                }))) return
                setBusy('delete')
                try {
                  await api.post('/auth/me/delete-request')
                  const code = await prompt({
                    title: 'Confirm account deletion',
                    description: 'Check your inbox for a 6-digit code. Paste it below to permanently delete your account.',
                    placeholder: '000000',
                    required: true,
                    maxLength: 6,
                    confirmLabel: 'Delete permanently',
                  })
                  if (code === null) { setBusy(null); return }
                  await api.delete('/auth/me', { data: { code } })
                  toast.success('Your account has been erased.')
                  await logout()
                } catch (e: any) {
                  toast.error(e?.response?.data?.detail || 'Deletion failed')
                } finally { setBusy(null) }
              }}
              disabled={busy === 'delete'}
              data-testid="delete-account-btn"
              className="shrink-0 text-sm bg-red-50 hover:bg-red-100 disabled:bg-slate-50 text-red-700 font-semibold px-4 py-2 rounded-lg border border-red-200"
            >
              {busy === 'delete' ? 'Sending…' : 'Delete account'}
            </button>
          </div>
        </div>
<<<<<<< HEAD
=======
        <ConfirmDialog />
>>>>>>> origin/main
      </div>
    </div>
  )
}

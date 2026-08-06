/**
 * Iter 30i — 2FA (TOTP) self-service tab for Organization Settings.
 *
 * Flow:
 *   1. If disabled: "Enable 2FA" button → /setup-init → shows QR + secret
 *      + a 6-digit code input. Submit → /setup → shows recovery codes
 *      (one time only).
 *   2. If enabled: shows an "Enabled since ..." pill + "Disable" button.
 *      Disable requires re-entering password + a fresh TOTP code.
 */
import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { Shield, ShieldCheck, ShieldOff, KeyRound, Copy, Check } from 'lucide-react'
import { toast } from 'sonner'

type Status = { enabled: boolean; enabled_at: string | null }
type SetupInit = { secret: string; otpauth_url: string; qr_data_url: string }

export function SecurityTab() {
  const [status, setStatus] = useState<Status | null>(null)
  const [phase, setPhase] = useState<'idle' | 'setup' | 'recovery'>('idle')
  const [init, setInit] = useState<SetupInit | null>(null)
  const [code, setCode] = useState('')
  const [recovery, setRecovery] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [disablePwd, setDisablePwd] = useState('')
  const [disableCode, setDisableCode] = useState('')
  const [copied, setCopied] = useState(false)

  const load = () => api.get('/auth/2fa/status').then(r => setStatus(r.data))
  useEffect(() => { load() }, [])

  const startSetup = async () => {
    setBusy(true)
    try {
      const r = await api.post('/auth/2fa/setup-init')
      setInit(r.data)
      setPhase('setup')
    } catch (e: any) {
      toast.error(e?.response?.data?.error?.message || 'Could not start 2FA setup')
    } finally { setBusy(false) }
  }

  const completeSetup = async () => {
    if (!init) return
    setBusy(true)
    try {
      const r = await api.post('/auth/2fa/setup', { secret: init.secret, code: code.trim() })
      setRecovery(r.data.recovery_codes)
      setPhase('recovery')
      setCode('')
      setInit(null)
      await load()
      toast.success('2FA enabled — save your recovery codes now')
    } catch (e: any) {
      toast.error(e?.response?.data?.error?.message || 'Invalid code — please try again')
    } finally { setBusy(false) }
  }

  const disable = async () => {
    setBusy(true)
    try {
      await api.post('/auth/2fa/disable', { password: disablePwd, code: disableCode.trim() })
      setDisablePwd('')
      setDisableCode('')
      await load()
      toast.success('2FA disabled')
    } catch (e: any) {
      toast.error(e?.response?.data?.error?.message || e?.response?.data?.detail || 'Could not disable 2FA')
    } finally { setBusy(false) }
  }

  const copyRecovery = () => {
    navigator.clipboard.writeText(recovery.join('\n'))
    setCopied(true); setTimeout(() => setCopied(false), 1500)
  }

  if (!status) return <div className="p-4"><div className="w-6 h-6 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>

  return (
    <div className="max-w-3xl" data-testid="security-tab">
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center">
            {status.enabled ? <ShieldCheck className="h-6 w-6 text-emerald-600" /> : <Shield className="h-6 w-6 text-slate-500" />}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-slate-900">Two-factor authentication</h2>
              {status.enabled ? (
                <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full border border-emerald-200">
                  <ShieldCheck className="h-3 w-3" /> Enabled
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full border border-slate-200">
                  Off
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-1">
              {status.enabled
                ? `Enabled ${status.enabled_at ? new Date(status.enabled_at).toLocaleString() : ''}. You'll be prompted for a 6-digit code on every sign-in.`
                : "Add an extra layer of security. You'll need an authenticator app like Google Authenticator, Authy, or 1Password."}
            </p>
          </div>
        </div>

        {/* Phase: idle + disabled → offer enable */}
        {phase === 'idle' && !status.enabled && (
          <div className="mt-6">
            <button
              onClick={startSetup}
              disabled={busy}
              data-testid="totp-enable-btn"
              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg shadow-sm disabled:opacity-50"
            >
              <ShieldCheck className="h-4 w-4" /> Enable 2FA
            </button>
          </div>
        )}

        {/* Phase: setup — show QR + code input */}
        {phase === 'setup' && init && (
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p className="text-sm font-medium text-slate-700 mb-2">1. Scan this QR with your authenticator</p>
              <img src={init.qr_data_url} alt="TOTP QR code" className="w-56 h-56 border border-slate-200 rounded-lg bg-white" data-testid="totp-qr" />
              <p className="text-xs text-slate-500 mt-2">
                Can&apos;t scan? Enter this secret manually:
              </p>
              <code className="block mt-1 text-xs bg-slate-50 border border-slate-200 rounded px-2 py-1 font-mono break-all" data-testid="totp-secret">
                {init.secret}
              </code>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-700 mb-2">2. Enter the 6-digit code shown</p>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                value={code}
                onChange={e => setCode(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                data-testid="totp-code-input"
                className="w-full text-2xl font-mono tracking-widest text-center px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <div className="flex gap-2 mt-4">
                <button
                  onClick={completeSetup}
                  disabled={busy || code.length !== 6}
                  data-testid="totp-confirm-btn"
                  className="flex-1 inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-40"
                >
                  <Check className="h-4 w-4" /> Confirm
                </button>
                <button
                  onClick={() => { setPhase('idle'); setInit(null); setCode('') }}
                  className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Phase: recovery — show one-time codes */}
        {phase === 'recovery' && recovery.length > 0 && (
          <div className="mt-6 border border-amber-200 bg-amber-50 rounded-lg p-4" data-testid="totp-recovery-codes">
            <div className="flex items-start gap-3">
              <KeyRound className="h-5 w-5 text-amber-700 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-amber-900">Save your recovery codes</p>
                <p className="text-xs text-amber-800 mt-1">
                  Each code works ONCE if you lose access to your authenticator. Store them somewhere safe — they will not be shown again.
                </p>
                <div className="grid grid-cols-2 gap-2 mt-3 font-mono text-sm">
                  {recovery.map((c, i) => (
                    <code key={i} className="bg-white border border-amber-200 rounded px-2 py-1 text-center">{c}</code>
                  ))}
                </div>
                <div className="flex gap-2 mt-3">
                  <button onClick={copyRecovery} data-testid="totp-copy-recovery-btn"
                    className="inline-flex items-center gap-2 text-xs font-semibold text-amber-900 border border-amber-300 bg-white hover:bg-amber-100 px-3 py-1.5 rounded-lg">
                    {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    {copied ? 'Copied' : 'Copy all'}
                  </button>
                  <button onClick={() => setPhase('idle')} className="text-xs font-semibold text-slate-600 px-3 py-1.5 rounded-lg hover:bg-white">
                    Done — I have saved them
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Enabled → show disable form */}
        {status.enabled && phase === 'idle' && (
          <div className="mt-6 border-t border-slate-200 pt-6">
            <p className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
              <ShieldOff className="h-4 w-4" /> Disable 2FA
            </p>
            <p className="text-xs text-slate-500 mb-3">
              Requires your account password AND a fresh TOTP code (or a recovery code).
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                type="password"
                value={disablePwd}
                onChange={e => setDisablePwd(e.target.value)}
                placeholder="Password"
                data-testid="totp-disable-password"
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <input
                type="text"
                value={disableCode}
                onChange={e => setDisableCode(e.target.value)}
                placeholder="TOTP code or recovery code"
                data-testid="totp-disable-code"
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
              />
            </div>
            <button
              onClick={disable}
              disabled={busy || !disablePwd || !disableCode}
              data-testid="totp-disable-btn"
              className="mt-3 inline-flex items-center gap-2 text-sm font-semibold px-4 py-2 border border-rose-300 text-rose-700 hover:bg-rose-50 rounded-lg disabled:opacity-40"
            >
              <ShieldOff className="h-4 w-4" /> Disable 2FA
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

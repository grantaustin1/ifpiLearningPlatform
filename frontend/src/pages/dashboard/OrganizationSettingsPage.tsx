import { useEffect, useState, useRef } from 'react'
import { api } from 'lib/api'
import { Save, Palette, Award, Building2, Eye, Upload, Sparkles, Check, Mail, Send, Trophy, FileText } from 'lucide-react'
import { toast } from 'sonner'
import { DocumentsTab } from './OrganizationDocumentsTab'

type SettingsTab = 'branding' | 'documents'

export default function OrganizationSettingsPage() {
  const [org, setOrg] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [themes, setThemes] = useState<any[]>([])
  const [applyingTheme, setApplyingTheme] = useState<string | null>(null)
  const [tab, setTab] = useState<SettingsTab>('branding')
  const logoInputRef = useRef<HTMLInputElement>(null)
  const sigInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.get('/organization').then(r => setOrg(r.data))
    api.get('/organization/themes').then(r => setThemes(r.data)).catch(() => {})
  }, [])

  const applyTheme = async (slug: string) => {
    setApplyingTheme(slug)
    try {
      await api.post(`/organization/apply-theme/${slug}`)
      const r = await api.get('/organization')
      setOrg(r.data)
      toast.success(`Applied "${themes.find(t => t.slug === slug)?.name}" theme`)
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Could not apply theme') }
    finally { setApplyingTheme(null) }
  }

  // Auto-debounced live preview: re-render the cert PDF 500ms after the
  // admin stops typing/changing branding fields. Initial render is skipped
  // until the org is loaded and the first manual preview is rendered.
  const previewKey = JSON.stringify({
    n: org?.name, l: org?.logo_url, a: org?.cert_accent_color,
    p: org?.primary_color, st: org?.cert_signature_text,
    si: org?.cert_signature_image_url, f: org?.cert_footer_text,
  })
  useEffect(() => {
    if (!org) return
    if (!previewUrl) return // wait until user clicks "Live preview" once
    const t = setTimeout(() => { livePreview() }, 500)
    return () => clearTimeout(t)
  }, [previewKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    setSaving(true)
    try {
      await api.patch('/organization', {
        name: org.name, logo_url: org.logo_url, primary_color: org.primary_color,
        description: org.description,
        cert_accent_color: org.cert_accent_color,
        cert_signature_text: org.cert_signature_text,
        cert_signature_image_url: org.cert_signature_image_url,
        cert_footer_text: org.cert_footer_text,
      })
      toast.success('Settings saved')
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Save failed') }
    finally { setSaving(false) }
  }

  const livePreview = async () => {
    setPreviewing(true)
    try {
      const r = await api.post('/admin/cert-preview', {
        organisation_name: org.name, organisation_logo_url: org.logo_url,
        accent_color: org.cert_accent_color || org.primary_color || '#6366f1',
        signature_text: org.cert_signature_text,
        signature_image_url: org.cert_signature_image_url,
        footer_text: org.cert_footer_text,
      }, { responseType: 'blob' })
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      setPreviewUrl(URL.createObjectURL(r.data))
    } catch (e: any) { toast.error('Could not render preview') }
    finally { setPreviewing(false) }
  }

  // Render the cert using a preset's values — no DB write.
  const previewPreset = async (preset: any) => {
    setPreviewing(true)
    try {
      const r = await api.post('/admin/cert-preview', {
        organisation_name: org.name,
        organisation_logo_url: org.logo_url,
        accent_color: preset.cert_accent_color,
        signature_text: org.cert_signature_text || preset.cert_signature_text_suggestion,
        signature_image_url: org.cert_signature_image_url,
        footer_text: org.cert_footer_text || preset.cert_footer_text_suggestion,
      }, { responseType: 'blob' })
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      setPreviewUrl(URL.createObjectURL(r.data))
      toast.message(`Previewing "${preset.name}" — click Apply to keep it`)
    } catch (e: any) { toast.error('Could not render preview') }
    finally { setPreviewing(false) }
  }

  const uploadImage = async (file: File, target: 'logo' | 'signature') => {
    if (file.size > 5 * 1024 * 1024) { toast.error('Max 5 MB'); return }
    const fd = new FormData(); fd.append('file', file)
    try {
      const r = await api.post('/uploads/image', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      if (target === 'logo') setOrg({ ...org, logo_url: r.data.url })
      else setOrg({ ...org, cert_signature_image_url: r.data.url })
      toast.success('Uploaded')
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Upload failed') }
  }

  if (!org) return <div className="p-8"><div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>

  return (
    <div className="p-8" data-testid="org-settings-page">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 font-display">Academy Settings</h1>
        <p className="text-slate-500 mt-1">Branding, certificate template, and downloadable documentation.</p>
      </div>

      {/* Tab bar — Iter 30e adds the Documents tab */}
      <div className="border-b border-slate-200 mb-6 flex gap-1" data-testid="settings-tabs">
        {([
          { key: 'branding', label: 'Branding & Certificates', icon: Palette },
          { key: 'documents', label: 'Documents', icon: FileText },
        ] as const).map(t => {
          const Icon = t.icon
          const active = tab === t.key
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              data-testid={`settings-tab-${t.key}`}
              className={
                'inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition ' +
                (active
                  ? 'border-indigo-600 text-indigo-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-200')
              }
            >
              <Icon className="h-4 w-4" /> {t.label}
            </button>
          )
        })}
      </div>

      {tab === 'documents' ? (
        <DocumentsTab />
      ) : (
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
      <div className="xl:col-span-3">
        <div className="flex items-start justify-between mb-6">
          <div>
            <p className="text-slate-500">Update visual identity and certificate look-and-feel.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={livePreview} disabled={previewing} data-testid="cert-preview-btn"
              className="inline-flex items-center gap-2 border border-indigo-200 text-indigo-700 hover:bg-indigo-50 text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50">
              <Eye className="h-4 w-4" /> {previewing ? 'Rendering…' : 'Live preview'}
            </button>
            <button onClick={save} disabled={saving} data-testid="org-save-btn"
              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg shadow-sm disabled:opacity-50">
              <Save className="h-4 w-4" /> {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>

        <Section icon={Building2} title="Identity">
          <Field label="Academy name"><input value={org.name || ''} onChange={e => setOrg({...org, name: e.target.value})} className={inputCls} /></Field>
          <Field label="Description"><textarea rows={3} value={org.description || ''} onChange={e => setOrg({...org, description: e.target.value})} className={inputCls} /></Field>
          <Field label="Logo">
            <div className="flex gap-2">
              <input value={org.logo_url || ''} onChange={e => setOrg({...org, logo_url: e.target.value})} placeholder="URL or upload below" className={`flex-1 ${inputCls}`} data-testid="org-logo-url" />
              <button type="button" onClick={() => logoInputRef.current?.click()} data-testid="logo-upload-btn"
                className="inline-flex items-center gap-1 border border-slate-200 hover:bg-slate-50 rounded-lg px-3 text-xs font-medium"><Upload className="h-3.5 w-3.5" /> Upload</button>
              <input ref={logoInputRef} type="file" accept="image/*" className="hidden" onChange={e => e.target.files?.[0] && uploadImage(e.target.files[0], 'logo')} />
            </div>
          </Field>
          {org.logo_url && (
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center gap-3 mt-2">
              <img src={org.logo_url} alt="logo preview" className="h-10 w-auto" onError={(e: any) => e.target.style.display = 'none'} />
              <span className="text-xs text-slate-500">Logo preview</span>
            </div>
          )}
        </Section>

        <Section icon={Sparkles} title="Theme presets" help="Hover for Preview / Apply. Preview renders the cert with the preset's colors WITHOUT saving. Apply persists.">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2" data-testid="theme-presets-grid">
            {themes.map((t: any) => {
              const active = org.theme_preset === t.slug
              const busy = applyingTheme === t.slug
              return (
                <div key={t.slug}
                  data-testid={`theme-preset-${t.slug}`}
                  className={`group relative text-left rounded-xl border p-3 flex items-start gap-3 transition ${active ? 'border-indigo-500 bg-indigo-50/40 ring-1 ring-indigo-200' : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm'} ${busy ? 'opacity-50' : ''}`}>
                  <div className="flex flex-col gap-1 pt-0.5">
                    <span className="w-5 h-5 rounded-full border border-white shadow-sm" style={{ background: t.primary_color }} />
                    <span className="w-5 h-5 rounded-full border border-white shadow-sm" style={{ background: t.cert_accent_color }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">{t.name}{active && <Check className="h-3.5 w-3.5 text-indigo-600" />}</p>
                    <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{t.description}</p>
                    <div className="flex gap-2 mt-2">
                      <button type="button" onClick={() => previewPreset(t)}
                        data-testid={`theme-preview-${t.slug}`}
                        className="text-[11px] font-medium text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50 px-2 py-1 rounded-md inline-flex items-center gap-1">
                        <Eye className="h-3 w-3" /> Preview
                      </button>
                      <button type="button" onClick={() => applyTheme(t.slug)} disabled={busy || active}
                        data-testid={`theme-apply-${t.slug}`}
                        className="text-[11px] font-medium text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 disabled:text-slate-400 disabled:hover:bg-transparent px-2 py-1 rounded-md inline-flex items-center gap-1">
                        <Check className="h-3 w-3" /> {active ? 'Applied' : 'Apply'}
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </Section>

        <Section icon={Palette} title="Brand colours">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Primary"><ColorInput value={org.primary_color || '#6366f1'} onChange={(v: string) => setOrg({...org, primary_color: v})} /></Field>
            <Field label="Cert accent" help="Defaults to Primary if empty">
              <ColorInput value={org.cert_accent_color || ''} onChange={(v: string) => setOrg({...org, cert_accent_color: v})} />
            </Field>
          </div>
        </Section>

        <Section icon={Award} title="Certificate template">
          <Field label="Signature text" help="e.g. 'Frances Moore, Chief Executive'">
            <input value={org.cert_signature_text || ''} onChange={e => setOrg({...org, cert_signature_text: e.target.value})} className={inputCls} data-testid="org-sig-text" />
          </Field>
          <Field label="Signature image" help="Optional PNG of a handwritten signature">
            <div className="flex gap-2">
              <input value={org.cert_signature_image_url || ''} onChange={e => setOrg({...org, cert_signature_image_url: e.target.value})} placeholder="URL or upload" className={`flex-1 ${inputCls}`} />
              <button type="button" onClick={() => sigInputRef.current?.click()} data-testid="sig-upload-btn"
                className="inline-flex items-center gap-1 border border-slate-200 hover:bg-slate-50 rounded-lg px-3 text-xs font-medium"><Upload className="h-3.5 w-3.5" /> Upload</button>
              <input ref={sigInputRef} type="file" accept="image/*" className="hidden" onChange={e => e.target.files?.[0] && uploadImage(e.target.files[0], 'signature')} />
            </div>
          </Field>
          <Field label="Footer text" help="Disclaimer or contact line shown small at the bottom of the cert">
            <textarea rows={2} value={org.cert_footer_text || ''} onChange={e => setOrg({...org, cert_footer_text: e.target.value})} className={inputCls} data-testid="org-footer-text" />
          </Field>
        </Section>

        <SmtpSection inputCls={inputCls} />
        <CohortSettingsSection inputCls={inputCls} />
      </div>

      <aside className="xl:col-span-2 sticky top-6 self-start">
        <h2 className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2"><Eye className="h-4 w-4 text-indigo-500" /> Certificate preview</h2>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden h-[520px]" data-testid="cert-preview-frame">
          {previewUrl ? (
            <iframe title="cert preview" src={previewUrl} className="w-full h-full" />
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400">
              <Eye className="h-8 w-8 mb-2 text-slate-300" />
              <p className="text-sm">Click <strong className="text-slate-600">Live preview</strong> to render a sample certificate using these settings.</p>
            </div>
          )}
        </div>
      </aside>
      </div>
      )}
    </div>
  )
}

const inputCls = "w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40"

function Section({ icon: Icon, title, help, children }: any) {
  return (
    <div className="bg-white rounded-2xl shadow-sm p-6 mb-4">
      <h2 className="text-sm font-semibold text-slate-900 mb-1 flex items-center gap-2"><Icon className="h-4 w-4 text-indigo-500" /> {title}</h2>
      {help && <p className="text-xs text-slate-500 mb-4">{help}</p>}
      {!help && <div className="mb-4" />}
      {children}
    </div>
  )
}

function Field({ label, help, children }: any) {
  return (
    <div className="mb-3">
      <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">{label}</label>
      {children}
      {help && <p className="text-[11px] text-slate-400 mt-1">{help}</p>}
    </div>
  )
}

function ColorInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex items-center gap-2">
      <input type="color" value={value || '#6366f1'} onChange={e => onChange(e.target.value)}
        className="w-10 h-9 rounded border border-slate-200" />
      <input value={value} onChange={e => onChange(e.target.value)} placeholder="#6366f1"
        className={`flex-1 ${inputCls} font-mono`} />
    </div>
  )
}


function SmtpSection({ inputCls }: { inputCls: string }) {
  const [cfg, setCfg] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [testTo, setTestTo] = useState('')
  const [testing, setTesting] = useState(false)

  useEffect(() => { api.get('/organization/smtp').then(r => setCfg(r.data)).catch(() => setCfg({})) }, [])
  if (!cfg) return null

  const save = async () => {
    setSaving(true)
    try {
      await api.put('/organization/smtp', cfg)
      toast.success('SMTP settings saved')
      const r = await api.get('/organization/smtp'); setCfg(r.data)
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Save failed') }
    finally { setSaving(false) }
  }

  const sendTest = async () => {
    if (!testTo) return toast.error('Enter a recipient first')
    setTesting(true)
    try {
      await api.post('/organization/smtp/test', { to: testTo })
      toast.success('Test email sent — check inbox')
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Test failed') }
    finally { setTesting(false) }
  }

  return (
    <Section icon={Mail} title="Email delivery (per-tenant SMTP)" help="When configured, outbox emails go via this server instead of the global stub. Leave host blank to disable.">
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">SMTP host</label>
          <input value={cfg.smtp_host || ''} onChange={e => setCfg({ ...cfg, smtp_host: e.target.value })} placeholder="smtp.sendgrid.net" className={inputCls} data-testid="smtp-host" />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Port</label>
          <input type="number" value={cfg.smtp_port || ''} onChange={e => setCfg({ ...cfg, smtp_port: Number(e.target.value) || null })} placeholder="587" className={inputCls} data-testid="smtp-port" />
        </div>
        <div className="flex items-end pb-2">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={cfg.smtp_use_tls ?? true} onChange={e => setCfg({ ...cfg, smtp_use_tls: e.target.checked })} data-testid="smtp-tls" className="rounded" />
            Use STARTTLS
          </label>
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Username</label>
          <input value={cfg.smtp_username || ''} onChange={e => setCfg({ ...cfg, smtp_username: e.target.value })} placeholder="apikey" className={inputCls} data-testid="smtp-user" />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Password {cfg.has_password && <span className="text-emerald-600 ml-1">(stored)</span>}</label>
          <input type="password" value={cfg.smtp_password || ''} onChange={e => setCfg({ ...cfg, smtp_password: e.target.value })} placeholder={cfg.has_password ? '••• stored, type to replace' : 'API key or password'} className={inputCls} data-testid="smtp-password" />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">From email</label>
          <input value={cfg.smtp_from_email || ''} onChange={e => setCfg({ ...cfg, smtp_from_email: e.target.value })} placeholder="learn@ifpi.org" className={inputCls} data-testid="smtp-from-email" />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">From name</label>
          <input value={cfg.smtp_from_name || ''} onChange={e => setCfg({ ...cfg, smtp_from_name: e.target.value })} placeholder="IFPI Learning" className={inputCls} data-testid="smtp-from-name" />
        </div>
      </div>
      <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100">
        <div className="flex items-center gap-2">
          <input value={testTo} onChange={e => setTestTo(e.target.value)} placeholder="test@example.com"
                 className={`w-56 ${inputCls}`} data-testid="smtp-test-to" />
          <button type="button" onClick={sendTest} disabled={testing || !cfg.is_configured}
                  data-testid="smtp-test-btn"
                  className="inline-flex items-center gap-1.5 border border-slate-200 hover:bg-slate-50 disabled:opacity-40 text-xs font-medium px-3 py-2 rounded-lg">
            <Send className="h-3.5 w-3.5" /> {testing ? 'Sending…' : 'Send test'}
          </button>
        </div>
        <button type="button" onClick={save} disabled={saving} data-testid="smtp-save"
                className="inline-flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50">
          <Save className="h-4 w-4" /> {saving ? 'Saving…' : 'Save SMTP'}
        </button>
      </div>
    </Section>
  )
}

function CohortSettingsSection({ inputCls }: { inputCls: string }) {
  const [threshold, setThreshold] = useState(75)
  const [webhook, setWebhook] = useState('')
  const [digestEnabled, setDigestEnabled] = useState(true)
  const [digestLastSent, setDigestLastSent] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [sendingDigest, setSendingDigest] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; status_code: number | null; provider: string; error: string | null } | null>(null)

  const loadOrg = () => api.get('/organization').then(r => {
    setThreshold(r.data.cohort_threshold || 75)
    setWebhook(r.data.cohort_celebration_webhook_url || '')
    setDigestEnabled(r.data.cohort_digest_enabled !== false)
    setDigestLastSent(r.data.cohort_digest_last_sent_at || null)
  })

  useEffect(() => { loadOrg() }, [])

  const save = async () => {
    setSaving(true)
    try {
      await api.put('/organization/cohort-settings', {
        cohort_threshold: threshold,
        cohort_celebration_webhook_url: webhook.trim() || null,
        cohort_digest_enabled: digestEnabled,
      })
      toast.success('Cohort settings saved')
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Save failed') }
    finally { setSaving(false) }
  }

  const detectProvider = (url: string): 'discord' | 'slack' | 'generic' | 'none' => {
    const u = (url || '').toLowerCase()
    if (!u) return 'none'
    if (u.includes('discord.com/api/webhooks') || u.includes('discordapp.com/api/webhooks')) return 'discord'
    if (u.includes('hooks.slack.com')) return 'slack'
    return 'generic'
  }
  const provider = detectProvider(webhook)
  const providerBadge: Record<string, { label: string; cls: string }> = {
    discord: { label: 'Discord', cls: 'bg-indigo-100 text-indigo-700 border-indigo-200' },
    slack:   { label: 'Slack',   cls: 'bg-fuchsia-100 text-fuchsia-700 border-fuchsia-200' },
    generic: { label: 'Custom',  cls: 'bg-slate-100 text-slate-700 border-slate-200' },
    none:    { label: 'None',    cls: 'bg-slate-50 text-slate-400 border-slate-200' },
  }
  const pb = providerBadge[provider]

  const sendTestPing = async () => {
    const url = webhook.trim()
    if (!url) { toast.error('Paste a webhook URL first'); return }
    setTesting(true)
    setTestResult(null)
    try {
      const r = await api.post('/organization/cohort-settings/test-webhook', { webhook_url: url })
      setTestResult(r.data)
      if (r.data.ok) toast.success(`Ping delivered (${r.data.provider} · ${r.data.status_code})`)
      else toast.error(`Webhook responded ${r.data.status_code ?? 'no-status'} — see details below`)
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || 'Request failed'
      setTestResult({ ok: false, status_code: null, provider, error: detail })
      toast.error(detail)
    } finally { setTesting(false) }
  }

  const sendDigestNow = async () => {
    setSendingDigest(true)
    try {
      const r = await api.post('/organization/cohort-digest/send-now')
      toast.success(`Digest queued to ${r.data.queued} admin${r.data.queued === 1 ? '' : 's'} — ${r.data.total_cohorts} cohort${r.data.total_cohorts === 1 ? '' : 's'} (${r.data.past} past · ${r.data.nudge} nudge)`)
      await loadOrg()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Send failed')
    } finally { setSendingDigest(false) }
  }

  const fmtLastSent = (iso: string | null): string => {
    if (!iso) return 'never'
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return 'never'
    return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
  }

  return (
    <Section icon={Trophy} title="Cohort milestone celebrations" help="When a cohort hits this completion %, IFPI emails every admin + (optionally) pings a Discord/Slack channel. Idempotent — fires once per cohort.">
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">Completion threshold: <span className="text-indigo-600" data-testid="cohort-threshold-value">{threshold}%</span></label>
          <input type="range" min={1} max={100} value={threshold} onChange={e => setThreshold(Number(e.target.value))}
            data-testid="cohort-threshold-slider"
            className="w-full accent-indigo-500" />
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wide">Discord / Slack webhook (optional)</label>
            <span data-testid="cohort-webhook-provider" className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border ${pb.cls}`}>{pb.label}</span>
          </div>
          <div className="flex gap-2">
            <input value={webhook} onChange={e => { setWebhook(e.target.value); setTestResult(null) }} placeholder="https://discord.com/api/webhooks/… or https://hooks.slack.com/…"
              data-testid="cohort-webhook"
              className={`${inputCls} font-mono text-xs flex-1`} />
            <button type="button" onClick={sendTestPing} disabled={testing || !webhook.trim()}
              data-testid="cohort-webhook-test"
              className="inline-flex items-center gap-1.5 border border-slate-200 hover:bg-slate-50 disabled:opacity-40 text-xs font-medium px-3 py-2 rounded-lg whitespace-nowrap">
              <Send className="h-3.5 w-3.5" /> {testing ? 'Pinging…' : 'Send test ping'}
            </button>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Slack/Discord both accept the same payload — paste the incoming-webhook URL from your channel settings.</p>
          {testResult && (
            <div data-testid="cohort-webhook-test-result"
              className={`mt-2 text-xs rounded-lg border px-3 py-2 ${testResult.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-rose-200 bg-rose-50 text-rose-800'}`}>
              {testResult.ok ? (
                <><Check className="inline h-3.5 w-3.5 mr-1" /> Delivered to <span className="font-semibold capitalize">{testResult.provider}</span> · HTTP {testResult.status_code}</>
              ) : (
                <>✗ Failed{testResult.status_code ? ` (HTTP ${testResult.status_code})` : ''}{testResult.error ? ` — ${testResult.error}` : ''}</>
              )}
            </div>
          )}
        </div>

        {/* Preview card — shows what the celebration message will look like */}
        <details className="rounded-lg border border-slate-200 bg-slate-50/50 group" data-testid="cohort-preview-toggle">
          <summary className="cursor-pointer select-none text-xs font-semibold text-slate-600 px-3 py-2 flex items-center gap-1.5">
            <Eye className="h-3.5 w-3.5" /> Preview celebration message
          </summary>
          <div className="px-3 pb-3 pt-1" data-testid="cohort-preview-content">
            <div className="rounded-md border border-slate-200 bg-white px-3 py-2 font-mono text-[11px] text-slate-700 leading-relaxed">
              🎉 <strong>Your Academy</strong> cohort <strong>Spring-2026</strong> hit <strong>{threshold}%</strong> completion!
              <br />
              <span className="text-slate-500">(24/30 enrolments, avg score 87.4%, 12 certs)</span>
            </div>
            <p className="text-[10px] text-slate-400 mt-1.5">Same payload sent to both Slack (`text`) and Discord (`content`) — works with either provider.</p>
          </div>
        </details>

        {/* Weekly digest — predictive nudge */}
        <div className="rounded-lg border border-indigo-100 bg-gradient-to-br from-indigo-50/60 to-white px-4 py-3" data-testid="cohort-digest-block">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-indigo-600" />
                <span className="text-sm font-semibold text-slate-800">Weekly cohort digest</span>
                <span data-testid="cohort-digest-status" className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border ${digestEnabled ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-100 text-slate-500 border-slate-200'}`}>
                  {digestEnabled ? 'ON' : 'OFF'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                Every Monday 09:00 UTC, every admin gets a recap of cohorts past the threshold + a nudge for any within 15pp of it.
                <br />
                Last sent: <span className="font-mono text-slate-700" data-testid="cohort-digest-last-sent">{fmtLastSent(digestLastSent)}</span>
              </p>
            </div>
            <div className="flex flex-col gap-1.5 items-end">
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={digestEnabled} onChange={e => setDigestEnabled(e.target.checked)}
                  data-testid="cohort-digest-toggle"
                  className="rounded accent-indigo-500 h-4 w-4" />
                <span className="text-xs font-medium text-slate-700">{digestEnabled ? 'Enabled' : 'Disabled'}</span>
              </label>
              <button type="button" onClick={sendDigestNow} disabled={sendingDigest}
                data-testid="cohort-digest-send-now"
                className="inline-flex items-center gap-1.5 border border-indigo-200 hover:bg-indigo-50 disabled:opacity-40 text-xs font-medium px-3 py-1.5 rounded-lg whitespace-nowrap text-indigo-700">
                <Send className="h-3.5 w-3.5" /> {sendingDigest ? 'Sending…' : 'Send digest now'}
              </button>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button onClick={save} disabled={saving} data-testid="cohort-save"
            className="inline-flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50">
            <Save className="h-4 w-4" /> {saving ? 'Saving…' : 'Save cohort settings'}
          </button>
        </div>
      </div>
    </Section>
  )
}

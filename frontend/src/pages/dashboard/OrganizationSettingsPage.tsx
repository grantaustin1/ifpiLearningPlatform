import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { Save, Palette, Award, Building2 } from 'lucide-react'
import { toast } from 'sonner'

export default function OrganizationSettingsPage() {
  const [org, setOrg] = useState<any>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get('/organization').then(r => setOrg(r.data))
  }, [])

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

  if (!org) return <div className="p-8"><div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>

  return (
    <div className="p-8 max-w-3xl" data-testid="org-settings-page">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-display">Academy Settings</h1>
          <p className="text-slate-500 mt-1">Branding, certificate template, and contact info</p>
        </div>
        <button onClick={save} disabled={saving} data-testid="org-save-btn"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg shadow-sm disabled:opacity-50">
          <Save className="h-4 w-4" /> {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>

      <Section icon={Building2} title="Identity">
        <Field label="Academy name"><input value={org.name || ''} onChange={e => setOrg({...org, name: e.target.value})} className={inputCls} /></Field>
        <Field label="Description"><textarea rows={3} value={org.description || ''} onChange={e => setOrg({...org, description: e.target.value})} className={inputCls} /></Field>
        <Field label="Logo URL" help="Public URL to your logo PNG or SVG (used on certificates and emails)">
          <input value={org.logo_url || ''} onChange={e => setOrg({...org, logo_url: e.target.value})} placeholder="https://yourcdn.com/logo.png" className={inputCls} data-testid="org-logo-url" />
        </Field>
        {org.logo_url && (
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center gap-3 mt-2">
            <img src={org.logo_url} alt="logo preview" className="h-10 w-auto" onError={(e: any) => e.target.style.display = 'none'} />
            <span className="text-xs text-slate-500">Logo preview</span>
          </div>
        )}
      </Section>

      <Section icon={Palette} title="Brand colours">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Primary colour"><ColorInput value={org.primary_color || '#6366f1'} onChange={(v: string) => setOrg({...org, primary_color: v})} /></Field>
          <Field label="Certificate accent colour" help="Defaults to Primary if empty">
            <ColorInput value={org.cert_accent_color || ''} onChange={(v: string) => setOrg({...org, cert_accent_color: v})} />
          </Field>
        </div>
      </Section>

      <Section icon={Award} title="Certificate template">
        <Field label="Signature text" help="e.g. 'Frances Moore, Chief Executive'">
          <input value={org.cert_signature_text || ''} onChange={e => setOrg({...org, cert_signature_text: e.target.value})} className={inputCls} data-testid="org-sig-text" />
        </Field>
        <Field label="Signature image URL" help="Optional — a PNG of a handwritten signature">
          <input value={org.cert_signature_image_url || ''} onChange={e => setOrg({...org, cert_signature_image_url: e.target.value})} placeholder="https://yourcdn.com/signature.png" className={inputCls} />
        </Field>
        <Field label="Footer text" help="Disclaimer or contact line — shown small at the bottom of the certificate">
          <textarea rows={2} value={org.cert_footer_text || ''} onChange={e => setOrg({...org, cert_footer_text: e.target.value})} className={inputCls} data-testid="org-footer-text" />
        </Field>
      </Section>
    </div>
  )
}

const inputCls = "w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40"

function Section({ icon: Icon, title, children }: any) {
  return (
    <div className="bg-white rounded-2xl shadow-sm p-6 mb-4">
      <h2 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2"><Icon className="h-4 w-4 text-indigo-500" /> {title}</h2>
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

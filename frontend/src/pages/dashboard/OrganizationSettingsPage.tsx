import { useEffect, useState, useRef } from 'react'
import { api, API_BASE, getAccessToken } from 'lib/api'
import { Save, Palette, Award, Building2, Eye, Upload } from 'lucide-react'
import { toast } from 'sonner'

export default function OrganizationSettingsPage() {
  const [org, setOrg] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const logoInputRef = useRef<HTMLInputElement>(null)
  const sigInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { api.get('/organization').then(r => setOrg(r.data)) }, [])

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewKey])

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
    <div className="p-8 grid grid-cols-1 xl:grid-cols-5 gap-6" data-testid="org-settings-page">
      <div className="xl:col-span-3">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 font-display">Academy Settings</h1>
            <p className="text-slate-500 mt-1">Branding & certificate template</p>
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

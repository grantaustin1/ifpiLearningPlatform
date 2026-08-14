import { useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from 'lib/api'
import { MessageSquarePlus, X, Send, ImagePlus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

const CATEGORIES = [
  { value: 'BUG', label: '🐞 Bug' },
  { value: 'IDEA', label: '💡 Idea' },
  { value: 'OTHER', label: '💬 Other' },
]

export function FeedbackWidget() {
  const [open, setOpen] = useState(false)
  const [category, setCategory] = useState('BUG')
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [shot, setShot] = useState<File | null>(null)
  const [shotPreview, setShotPreview] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const location = useLocation()

  const pickShot = (f: File | undefined) => {
    if (!f) return
    if (!f.type.startsWith('image/')) { toast.error('Please attach an image file'); return }
    if (f.size > 5 * 1024 * 1024) { toast.error('Screenshot too large (max 5MB)'); return }
    if (shotPreview) URL.revokeObjectURL(shotPreview)
    setShot(f)
    setShotPreview(URL.createObjectURL(f))
  }

  const clearShot = () => {
    if (shotPreview) URL.revokeObjectURL(shotPreview)
    setShot(null); setShotPreview(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  const submit = async () => {
    if (message.trim().length < 3) { toast.error('Tell us a little more first'); return }
    setSending(true)
    try {
      let screenshot_url: string | null = null
      if (shot) {
        const fd = new FormData()
        fd.append('file', shot)
        const r = await api.post('/feedback/screenshot', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
        screenshot_url = r.data.url
      }
      await api.post('/feedback', { message: message.trim(), category, page: location.pathname, screenshot_url })
      toast.success('Feedback sent — thank you!')
      setMessage(''); clearShot(); setOpen(false)
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'Could not send feedback') }
    finally { setSending(false) }
  }

  return (
    <>
      <button onClick={() => setOpen(true)} data-testid="feedback-widget-btn"
        title="Report an issue"
        className="fixed bottom-5 right-5 z-40 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full p-3.5 shadow-lg shadow-indigo-200 hover:scale-105 transition-all">
        <MessageSquarePlus className="h-5 w-5" />
      </button>
      {open && (
        <div className="fixed bottom-20 right-5 z-50 w-80 bg-white rounded-2xl shadow-2xl border border-slate-200" data-testid="feedback-widget-panel">
          <div className="px-4 py-3 border-b flex items-center justify-between">
            <p className="text-sm font-semibold text-slate-900">Report an issue</p>
            <button onClick={() => setOpen(false)} data-testid="feedback-widget-close"><X className="h-4 w-4 text-slate-400" /></button>
          </div>
          <div className="p-4 space-y-3"
            onPaste={e => { const f = Array.from(e.clipboardData.files).find(x => x.type.startsWith('image/')); if (f) { pickShot(f); e.preventDefault() } }}>
            <div className="flex gap-1.5">
              {CATEGORIES.map(c => (
                <button key={c.value} onClick={() => setCategory(c.value)}
                  data-testid={`feedback-cat-${c.value.toLowerCase()}`}
                  className={`flex-1 text-xs font-medium rounded-lg py-1.5 border transition-colors ${category === c.value ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-200 text-slate-500 hover:border-slate-300'}`}>
                  {c.label}
                </button>
              ))}
            </div>
            <textarea value={message} onChange={e => setMessage(e.target.value)} rows={4}
              placeholder="What happened? What did you expect?"
              data-testid="feedback-message"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm resize-none" />
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
              data-testid="feedback-screenshot-input"
              onChange={e => pickShot(e.target.files?.[0])} />
            {shotPreview ? (
              <div className="relative rounded-lg border border-slate-200 overflow-hidden" data-testid="feedback-screenshot-preview">
                <img src={shotPreview} alt="Screenshot preview" className="w-full max-h-32 object-cover" />
                <button onClick={clearShot} data-testid="feedback-screenshot-remove"
                  title="Remove screenshot"
                  className="absolute top-1.5 right-1.5 bg-slate-900/70 hover:bg-red-600 text-white rounded-md p-1 transition-colors">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : (
              <button onClick={() => fileRef.current?.click()} data-testid="feedback-screenshot-attach"
                className="w-full inline-flex items-center justify-center gap-1.5 border border-dashed border-slate-300 hover:border-indigo-400 hover:text-indigo-600 text-slate-500 text-xs font-medium rounded-lg py-2 transition-colors">
                <ImagePlus className="h-3.5 w-3.5" /> Attach screenshot (or paste)
              </button>
            )}
            <p className="text-[10px] text-slate-400">Page: {location.pathname}</p>
            <button onClick={submit} disabled={sending} data-testid="feedback-submit"
              className="w-full inline-flex items-center justify-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg py-2 disabled:opacity-50">
              <Send className="h-3.5 w-3.5" /> {sending ? 'Sending…' : 'Send feedback'}
            </button>
          </div>
        </div>
      )}
    </>
  )
}

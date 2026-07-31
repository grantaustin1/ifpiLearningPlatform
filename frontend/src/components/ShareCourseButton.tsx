import { useState } from 'react'
import { Share2, Check, Link2, Globe } from 'lucide-react'
import { toast } from 'sonner'

export function copyText(text: string, message: string) {
  const done = () => toast.success(message)
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done))
  } else fallbackCopy(text, done)
}

function fallbackCopy(text: string, done: () => void) {
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.position = 'fixed'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  ta.select()
  try { document.execCommand('copy'); done() } finally { document.body.removeChild(ta) }
}

export const ShareCourseButton = ({ courseId, mode = 'icon', className = '' }:
{ courseId: number; mode?: 'icon' | 'menu' | 'button'; className?: string }) => {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const publicUrl = `${window.location.origin}/catalog/${courseId}`
  const inAppUrl = `${window.location.origin}/learn/${courseId}`

  const copyPublic = () => {
    copyText(publicUrl, 'Public course link copied — anyone can open it')
    setCopied(true); setTimeout(() => setCopied(false), 2000)
  }

  if (mode === 'button') {
    return (
      <button onClick={copyPublic} data-testid={`share-course-btn-${courseId}`}
        className={`w-full inline-flex items-center justify-center gap-2 border border-slate-200 hover:border-indigo-300 hover:text-indigo-700 text-slate-600 font-semibold px-4 py-2.5 rounded-xl text-sm transition-colors ${className}`}>
        {copied ? <Check className="h-4 w-4 text-emerald-500" /> : <Share2 className="h-4 w-4" />}
        {copied ? 'Link copied!' : 'Share this course'}
      </button>
    )
  }

  if (mode === 'menu') {
    return (
      <div className="relative">
        <button onClick={() => setOpen(o => !o)} title="Share course" data-testid={`share-course-btn-${courseId}`}
          className={`inline-flex items-center justify-center text-xs border border-slate-200 hover:border-slate-300 rounded-lg px-2.5 py-1.5 font-medium ${className}`}>
          <Share2 className="h-3.5 w-3.5" />
        </button>
        {open && (
          <>
            <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
            <div className="absolute right-0 bottom-full mb-1 z-40 bg-white border border-slate-200 rounded-xl shadow-lg py-1 w-48" data-testid={`share-menu-${courseId}`}>
              <button onClick={() => { copyText(publicUrl, 'Public link copied — no sign-in needed'); setOpen(false) }}
                data-testid={`share-public-${courseId}`}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 text-left">
                <Globe className="h-3.5 w-3.5 text-indigo-500" /> Copy public link
              </button>
              <button onClick={() => { copyText(inAppUrl, 'In-app link copied — recipient signs in first'); setOpen(false) }}
                data-testid={`share-inapp-${courseId}`}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 text-left">
                <Link2 className="h-3.5 w-3.5 text-slate-400" /> Copy in-app link
              </button>
            </div>
          </>
        )}
      </div>
    )
  }

  return (
    <button onClick={copyPublic} title="Copy public course link" data-testid={`share-course-btn-${courseId}`}
      className={`inline-flex items-center justify-center rounded-lg p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors ${className}`}>
      {copied ? <Check className="h-4 w-4 text-emerald-500" /> : <Share2 className="h-4 w-4" />}
    </button>
  )
}

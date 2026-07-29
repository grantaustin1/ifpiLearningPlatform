import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { X, Check, RotateCcw } from 'lucide-react'
import { api } from 'lib/api'
import { safeSvg } from 'lib/sanitize'

/**
 * SubscriptionModal — Renders the calendar-subscription URL, QR SVG,
 * and (admin-only) rotate-secret button.
 *
 * Extracted from LiveSessionsPage.tsx in iter-27 as part of the file
 * size reduction refactor.
 */
export function SubscriptionModal({ url, kind, isAdmin, onClose, onRotate }: {
  url: string
  kind: 'admin' | 'learner' | 'my_rsvps'
  isAdmin: boolean
  onClose: () => void
  onRotate: () => void
}) {
  const [copied, setCopied] = useState(false)
  const [qrSvg, setQrSvg] = useState<string | null>(null)

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true); setTimeout(() => setCopied(false), 2000)
      toast.success('URL copied')
    } catch { toast.error('Clipboard blocked — select and copy manually') }
  }

  useEffect(() => {
    // Fetch the SVG with the auth header (can't rely on <img src>)
    api.get('/live-sessions/subscribe-url/qr', {
      params: { kind }, responseType: 'text',
    }).then(r => setQrSvg(r.data)).catch(() => { /* silent */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, url])

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" data-testid="subscription-modal">
      <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <div>
            <h2 className="font-semibold text-slate-900">Subscribe to your live sessions</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Paste this URL into Google Calendar, Apple Calendar, or Outlook.
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" data-testid="close-subscription">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5 space-y-4">
          {qrSvg && (
            <div className="flex justify-center bg-slate-50 rounded-xl p-4" data-testid="subscription-qr">
              <div className="w-48 h-48" dangerouslySetInnerHTML={{ __html: safeSvg(qrSvg) }} />
            </div>
          )}
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Calendar subscription URL</label>
            <div className="flex gap-2">
              <input readOnly value={url} data-testid="subscription-url-input"
                onClick={e => (e.target as HTMLInputElement).select()}
                className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-xs font-mono bg-slate-50" />
              <button onClick={copyToClipboard} data-testid="copy-subscription-url"
                className="inline-flex items-center gap-1 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium px-3 py-2 rounded-lg">
                {copied ? <Check className="h-3.5 w-3.5" /> : 'Copy'}
              </button>
            </div>
          </div>
          {isAdmin && (
            <div className="pt-4 border-t border-slate-100">
              <p className="text-xs font-semibold text-slate-700 mb-2">Danger zone</p>
              <button onClick={onRotate} data-testid="rotate-secret-btn"
                className="w-full inline-flex items-center justify-center gap-2 text-xs font-medium text-red-600 hover:bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
                <RotateCcw className="h-3.5 w-3.5" /> Rotate secret & revoke all outstanding URLs
              </button>
              <p className="text-[11px] text-slate-400 mt-2">
                Use this if a URL has been leaked. Users&apos; login sessions are unaffected — only calendar subscriptions need to be re-copied.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


export function SubscriptionKindPicker({ onPick, onClose }: {
  onPick: (kind: 'learner' | 'my_rsvps') => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" data-testid="subscription-kind-picker">
      <div className="bg-white rounded-2xl w-full max-w-sm shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <div>
            <h2 className="font-semibold text-slate-900">Which sessions?</h2>
            <p className="text-xs text-slate-500 mt-0.5">Choose what your calendar app should sync.</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" data-testid="close-kind-picker">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5 space-y-2">
          <button
            onClick={() => onPick('learner')}
            data-testid="pick-kind-learner"
            className="w-full text-left px-4 py-3 rounded-xl border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
          >
            <p className="font-medium text-slate-900 text-sm">All my cohort sessions</p>
            <p className="text-xs text-slate-500 mt-1">Everything visible to me — cohort-matched + open sessions.</p>
          </button>
          <button
            onClick={() => onPick('my_rsvps')}
            data-testid="pick-kind-my-rsvps"
            className="w-full text-left px-4 py-3 rounded-xl border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50 transition-colors"
          >
            <p className="font-medium text-slate-900 text-sm">Only sessions I&apos;ve RSVP&apos;d to</p>
            <p className="text-xs text-slate-500 mt-1">A tighter feed — updates live as you RSVP or cancel.</p>
          </button>
        </div>
      </div>
    </div>
  )
}

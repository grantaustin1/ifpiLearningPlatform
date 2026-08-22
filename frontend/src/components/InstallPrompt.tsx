import { useEffect, useState } from 'react'
import { Download, X, Share, PlusSquare } from 'lucide-react'

const DISMISS_KEY = 'ifpi_install_prompt_dismissed_v1'

const isIos = () => /iphone|ipad|ipod/i.test(navigator.userAgent)
const isStandalone = () =>
  window.matchMedia('(display-mode: standalone)').matches || (navigator as any).standalone === true

export function InstallPrompt() {
  const [deferred, setDeferred] = useState<any>(null)
  const [showIos, setShowIos] = useState(false)

  useEffect(() => {
    if (isStandalone() || localStorage.getItem(DISMISS_KEY)) return
    const onPrompt = (e: Event) => { e.preventDefault(); setDeferred(e) }
    window.addEventListener('beforeinstallprompt', onPrompt)
    if (isIos()) {
      const t = window.setTimeout(() => setShowIos(true), 2500)
      return () => { window.removeEventListener('beforeinstallprompt', onPrompt); window.clearTimeout(t) }
    }
    return () => window.removeEventListener('beforeinstallprompt', onPrompt)
  }, [])

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, new Date().toISOString())
    setDeferred(null); setShowIos(false)
  }

  const install = async () => {
    if (!deferred) return
    deferred.prompt()
    const { outcome } = await deferred.userChoice
    if (outcome === 'accepted') localStorage.setItem(DISMISS_KEY, 'installed')
    setDeferred(null)
  }

  if (!deferred && !showIos) return null

  return (
    <div className="fixed bottom-0 inset-x-0 z-50 p-3 md:hidden" data-testid="install-prompt"
      style={{ paddingBottom: 'calc(0.75rem + env(safe-area-inset-bottom))' }}>
      <div className="bg-ink-900 text-white rounded-2xl shadow-2xl border border-white/10 p-4 flex items-start gap-3">
        <img src="/icon-192.png" alt="IFPI Academy" className="w-10 h-10 rounded-xl flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold">Add IFPI Academy to your home screen</p>
          {deferred ? (
            <p className="text-xs text-slate-400 mt-0.5">Opens full-screen like a native app — one tap away.</p>
          ) : (
            <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1 flex-wrap">
              Tap <Share className="h-3.5 w-3.5 inline" /> Share, then <PlusSquare className="h-3.5 w-3.5 inline" /> “Add to Home Screen”.
            </p>
          )}
          {deferred && (
            <button onClick={install} data-testid="install-prompt-install"
              className="mt-2.5 inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg px-4 py-2 min-h-[36px] transition-colors">
              <Download className="h-3.5 w-3.5" /> Install app
            </button>
          )}
        </div>
        <button onClick={dismiss} data-testid="install-prompt-dismiss" className="text-slate-500 hover:text-white p-1 -mt-1 -mr-1">
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

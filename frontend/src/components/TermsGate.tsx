/**
 * Iter 30l — Global T&Cs acceptance gate.
 *
 * Mounted at the app shell. On every route change (post-login), fetches
 * /api/terms/current. If the user's org has a published version they
 * haven't accepted, renders a full-screen blocking modal with the
 * body_markdown + "I accept" button. Nothing else in the app is usable
 * until they accept.
 *
 * Skipped when: user not logged in / no published terms / already accepted.
 */
import { useEffect, useState } from 'react'
import { useAuth } from 'contexts/AuthContext'
import { api } from 'lib/api'
import { ScrollText, Check } from 'lucide-react'
import { toast } from 'sonner'

type State = {
  has_terms: boolean
  accepted: boolean
  terms?: { id: number; version: string; title: string; body_markdown: string; published_at: string }
}

export function TermsGate() {
  const { user } = useAuth()
  const [state, setState] = useState<State | null>(null)
  const [accepting, setAccepting] = useState(false)

  const load = async () => {
    try { const r = await api.get('/terms/current'); setState(r.data) }
    catch { /* ignore — endpoint may 401 during logout */ }
  }
  useEffect(() => { if (user) load() }, [user?.id])

  if (!user || !state?.has_terms || state.accepted) return null

  const accept = async () => {
    setAccepting(true)
    try {
      await api.post('/terms/accept', { terms_version_id: state.terms!.id })
      await load()
      toast.success('Thanks — you can now continue.')
    } catch (e: any) {
      toast.error(e?.response?.data?.error?.message || 'Could not record acceptance')
    } finally { setAccepting(false) }
  }

  const body = state.terms!.body_markdown

  return (
    <div className="fixed inset-0 z-[100] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4" data-testid="terms-gate">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-5 border-b border-slate-100 flex items-center gap-3">
          <div className="w-11 h-11 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center">
            <ScrollText className="h-5 w-5 text-indigo-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{state.terms!.title}</h2>
            <p className="text-xs text-slate-500">Version {state.terms!.version} · Please accept to continue</p>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4 prose prose-sm max-w-none" data-testid="terms-body">
          {/* Simple markdown rendering (no external lib): show as pre-line so headings + paragraphs are legible */}
          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 leading-relaxed">{body}</pre>
        </div>
        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-end">
          <button
            onClick={accept}
            disabled={accepting}
            data-testid="terms-accept-btn"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-5 py-2.5 rounded-lg shadow-sm disabled:opacity-50">
            {accepting
              ? <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              : <><Check className="h-4 w-4" /> I accept</>}
          </button>
        </div>
      </div>
    </div>
  )
}

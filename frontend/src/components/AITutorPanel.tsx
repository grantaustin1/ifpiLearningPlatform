/**
 * Iter 30m — Learner-facing AI Tutor panel.
 *
 * Slide-out panel triggered by a floating "Ask AI" button on the course
 * learn page. Uses /api/tutor/ask; scopes retrieval to the current course.
 * Persists chat history on the server so learners can resume mid-session.
 */
import { useEffect, useRef, useState } from 'react'
import { api } from 'lib/api'
import { Sparkles, X, Send, BookOpen, Loader2, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'

type Citation = {
  chunk_id: number | null
  document_id: number
  document_title: string
  snippet: string
  score: number | null
}

type Msg = {
  id: number
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
}

export function AITutorPanel({ courseId }: { courseId?: number }) {
  const [open, setOpen] = useState(false)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, open])

  const send = async (e: React.FormEvent) => {
    e.preventDefault()
    const q = input.trim()
    if (!q || busy) return
    setBusy(true)
    setInput('')
    // Optimistic user turn
    const optimisticId = Date.now()
    setMessages(m => [...m, { id: optimisticId, role: 'user', content: q }])
    try {
      const r = await api.post('/tutor/ask', {
        question: q,
        course_id: courseId,
        session_id: sessionId ?? undefined,
      })
      const { session_id, message_id, answer, citations, redaction_applied } = r.data
      if (!sessionId) setSessionId(session_id)
      setMessages(m => [
        ...m,
        { id: message_id, role: 'assistant', content: answer, citations },
      ])
      if (redaction_applied) {
        // Show a small privacy nudge the first time PII was redacted
        toast.success('Personal info was auto-redacted before sending.', {
          icon: <ShieldCheck className="h-4 w-4" />,
        })
      }
    } catch (err: any) {
      setMessages(m => [
        ...m,
        {
          id: Date.now(),
          role: 'assistant',
          content: err?.response?.data?.detail
            || err?.response?.data?.error?.message
            || 'Sorry — the tutor is temporarily unavailable. Please try again.',
        },
      ])
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        data-testid="ai-tutor-toggle"
        className="fixed bottom-6 right-6 z-40 group inline-flex items-center gap-2 bg-gradient-to-br from-indigo-600 to-fuchsia-600 hover:from-indigo-700 hover:to-fuchsia-700 text-white text-sm font-semibold px-4 py-3 rounded-full shadow-lg hover:shadow-xl transition-all hover:-translate-y-0.5">
        <Sparkles className="h-4 w-4" />
        Ask AI Tutor
      </button>
    )
  }

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full sm:w-[420px] bg-white shadow-2xl border-l border-slate-200 flex flex-col" data-testid="ai-tutor-panel">
      <header className="px-4 py-3 border-b border-slate-100 flex items-center gap-2 bg-gradient-to-br from-indigo-50 to-fuchsia-50">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-600 to-fuchsia-600 flex items-center justify-center">
          <Sparkles className="h-4 w-4 text-white" />
        </div>
        <div className="flex-1">
          <h2 className="text-sm font-semibold text-slate-900">AI Tutor</h2>
          <p className="text-[11px] text-slate-500">
            Grounded in this course&apos;s sources
          </p>
        </div>
        <button
          onClick={() => setOpen(false)}
          data-testid="ai-tutor-close"
          className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100">
          <X className="h-4 w-4" />
        </button>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50"
           data-testid="ai-tutor-messages">
        {messages.length === 0 && (
          <div className="text-center py-8 text-sm text-slate-400">
            <Sparkles className="h-6 w-6 mx-auto mb-2 text-indigo-300" />
            Ask anything about this course — I&apos;ll answer using the source material.
          </div>
        )}
        {messages.map(m => (
          <div key={m.id} data-testid={`tutor-msg-${m.role}`}
               className={m.role === 'user' ? 'flex justify-end' : ''}>
            <div className={`inline-block max-w-[90%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
              m.role === 'user'
                ? 'bg-indigo-600 text-white rounded-br-sm'
                : 'bg-white border border-slate-200 text-slate-800 rounded-bl-sm shadow-sm'
            }`}>
              <p className="whitespace-pre-wrap">{m.content}</p>
              {m.citations && m.citations.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-100 space-y-1">
                  {m.citations.map((c, i) => (
                    <div key={i} className="flex items-start gap-1 text-[11px] text-slate-500">
                      <BookOpen className="h-3 w-3 mt-0.5 flex-shrink-0 text-indigo-500" />
                      <div className="flex-1 min-w-0">
                        <span className="font-semibold text-slate-700">[{i+1}] {c.document_title}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="inline-flex items-center gap-2 px-3 py-2 rounded-2xl bg-white border border-slate-200 text-sm text-slate-500">
            <Loader2 className="h-3 w-3 animate-spin" /> Thinking…
          </div>
        )}
      </div>

      <form onSubmit={send} className="p-3 border-t border-slate-100 bg-white">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(e as any) }
            }}
            placeholder="Ask about this course…"
            rows={1}
            data-testid="ai-tutor-input"
            className="flex-1 px-3 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none" />
          <button type="submit" disabled={busy || !input.trim()}
                  data-testid="ai-tutor-send"
                  className="p-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white rounded-xl">
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="text-[10px] text-slate-400 mt-1.5 flex items-center gap-1">
          <ShieldCheck className="h-2.5 w-2.5" /> Personal info is auto-redacted before sending.
        </p>
      </form>
    </div>
  )
}

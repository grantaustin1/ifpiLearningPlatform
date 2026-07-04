import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { MessageSquare } from 'lucide-react'

/**
 * Iter 31 — Promise-returning text-input dialog (shadcn/Radix based).
 *
 * Replaces every `window.prompt()` in the codebase with an on-brand
 * modal that matches the rest of the UI. Same imperative ergonomics
 * as native prompt — call `await prompt({...})` and get a string,
 * or `null` if the user cancelled.
 *
 * Usage:
 *   const prompt = usePrompt()
 *   const reason = await prompt({ title: 'Reason for revocation', placeholder: '…' })
 *   if (reason === null) return  // user cancelled
 */
interface PromptOptions {
  title: string
  description?: string
  placeholder?: string
  defaultValue?: string
  confirmLabel?: string
  cancelLabel?: string
  required?: boolean
  multiline?: boolean
  maxLength?: number
}

interface Pending extends PromptOptions {
  resolve: (v: string | null) => void
}

interface Ctx {
  prompt: (opts: PromptOptions) => Promise<string | null>
}

const PromptContext = createContext<Ctx | null>(null)

export function usePrompt() {
  const ctx = useContext(PromptContext)
  if (!ctx) throw new Error('usePrompt must be used inside <PromptDialogProvider>')
  return ctx.prompt
}

export function PromptDialogProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null)
  const [value, setValue] = useState('')

  const prompt = useCallback((opts: PromptOptions) => {
    setValue(opts.defaultValue || '')
    return new Promise<string | null>(resolve => setPending({ ...opts, resolve }))
  }, [])

  const close = (accepted: boolean) => {
    if (pending) {
      if (!accepted) pending.resolve(null)
      else if (pending.required && !value.trim()) return
      else pending.resolve(value)
    }
    setPending(null)
    setValue('')
  }

  // Enter submits (single-line only) — Shift+Enter for newline in multiline
  useEffect(() => {
    if (!pending || pending.multiline) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); close(true) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pending, value])

  return (
    <PromptContext.Provider value={{ prompt }}>
      {children}
      <Dialog.Root open={!!pending} onOpenChange={o => { if (!o) close(false) }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-[100]" />
          <Dialog.Content
            data-testid="prompt-dialog"
            className="fixed left-1/2 top-1/2 z-[101] w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white shadow-2xl focus:outline-none"
          >
            {pending && (
              <>
                <div className="p-5 flex items-start gap-3 border-b border-slate-100">
                  <div className="shrink-0 rounded-full p-2 bg-indigo-50 text-indigo-600">
                    <MessageSquare className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <Dialog.Title
                      className="font-semibold text-slate-900"
                      data-testid="prompt-dialog-title"
                    >
                      {pending.title}
                    </Dialog.Title>
                    {pending.description && (
                      <Dialog.Description
                        className="text-sm text-slate-600 mt-1"
                        data-testid="prompt-dialog-description"
                      >
                        {pending.description}
                      </Dialog.Description>
                    )}
                  </div>
                </div>
                <div className="p-5">
                  {pending.multiline ? (
                    <textarea
                      value={value}
                      onChange={e => setValue(e.target.value.slice(0, pending.maxLength || 500))}
                      placeholder={pending.placeholder}
                      autoFocus
                      rows={4}
                      data-testid="prompt-dialog-input"
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                    />
                  ) : (
                    <input
                      type="text"
                      value={value}
                      onChange={e => setValue(e.target.value.slice(0, pending.maxLength || 255))}
                      placeholder={pending.placeholder}
                      autoFocus
                      data-testid="prompt-dialog-input"
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  )}
                  {pending.maxLength && (
                    <p className="text-xs text-slate-400 mt-1 text-right">
                      {value.length}/{pending.maxLength}
                    </p>
                  )}
                </div>
                <div className="flex justify-end gap-2 p-4 bg-slate-50 rounded-b-2xl">
                  <button
                    onClick={() => close(false)}
                    data-testid="prompt-dialog-cancel"
                    className="text-sm font-medium text-slate-700 px-4 py-2 rounded-lg hover:bg-slate-100"
                  >
                    {pending.cancelLabel || 'Cancel'}
                  </button>
                  <button
                    onClick={() => close(true)}
                    disabled={pending.required && !value.trim()}
                    data-testid="prompt-dialog-confirm"
                    className="text-sm font-semibold text-white px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed"
                  >
                    {pending.confirmLabel || 'OK'}
                  </button>
                </div>
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </PromptContext.Provider>
  )
}

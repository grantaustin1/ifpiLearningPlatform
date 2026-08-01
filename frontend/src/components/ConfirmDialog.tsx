<<<<<<< HEAD
import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { AlertTriangle, Info } from 'lucide-react'

/**
 * Iter 29 — Promise-returning confirm dialog (shadcn/Radix based).
 *
 * Replaces every `window.confirm()` in the codebase with an on-brand
 * modal that matches the rest of the UI. Same imperative ergonomics
 * as native confirm — call `await confirm({...})` and get a boolean.
 *
 * Usage:
 *   const confirm = useConfirm()
 *   if (!(await confirm({ title: 'Delete?', description: '…' }))) return
 *
 * The provider (`<ConfirmDialogProvider>`) sits at the app root and
 * portals a single dialog into the DOM. Multiple concurrent calls
 * queue naturally because each returns a fresh promise resolved when
 * the user picks a button.
 */
type Variant = 'default' | 'danger'

interface ConfirmOptions {
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: Variant
}

interface Pending extends ConfirmOptions {
  resolve: (v: boolean) => void
}

interface Ctx {
  confirm: (opts: ConfirmOptions) => Promise<boolean>
}

const ConfirmContext = createContext<Ctx | null>(null)

export function useConfirm() {
  const ctx = useContext(ConfirmContext)
  if (!ctx) {
    throw new Error('useConfirm must be used inside <ConfirmDialogProvider>')
  }
  return ctx.confirm
}

export function ConfirmDialogProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null)

  const confirm = useCallback((opts: ConfirmOptions) => {
    return new Promise<boolean>(resolve => setPending({ ...opts, resolve }))
  }, [])

  const close = (accepted: boolean) => {
    if (pending) pending.resolve(accepted)
    setPending(null)
  }

  // Keyboard: Enter confirms, Esc cancels — handled by Radix Dialog for Esc
  useEffect(() => {
    if (!pending) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter') { e.preventDefault(); close(true) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending])

  const isDanger = pending?.variant === 'danger'

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      <Dialog.Root open={!!pending} onOpenChange={o => { if (!o) close(false) }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-[100]" />
          <Dialog.Content
            data-testid="confirm-dialog"
            className="fixed left-1/2 top-1/2 z-[101] w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white shadow-2xl focus:outline-none"
          >
            {pending && (
              <>
                <div className="p-5 flex items-start gap-3 border-b border-slate-100">
                  <div className={`shrink-0 rounded-full p-2
                    ${isDanger ? 'bg-red-50 text-red-600' : 'bg-indigo-50 text-indigo-600'}`}>
                    {isDanger ? <AlertTriangle className="h-5 w-5" /> : <Info className="h-5 w-5" />}
                  </div>
                  <div className="min-w-0">
                    <Dialog.Title className="font-semibold text-slate-900" data-testid="confirm-dialog-title">
                      {pending.title}
                    </Dialog.Title>
                    {pending.description && (
                      <Dialog.Description className="text-sm text-slate-600 mt-1" data-testid="confirm-dialog-description">
                        {pending.description}
                      </Dialog.Description>
                    )}
                  </div>
                </div>
                <div className="flex justify-end gap-2 p-4 bg-slate-50 rounded-b-2xl">
                  <button
                    onClick={() => close(false)}
                    data-testid="confirm-dialog-cancel"
                    className="text-sm font-medium text-slate-700 px-4 py-2 rounded-lg hover:bg-slate-100"
                  >
                    {pending.cancelLabel || 'Cancel'}
                  </button>
                  <button
                    onClick={() => close(true)}
                    data-testid="confirm-dialog-confirm"
                    autoFocus
                    className={`text-sm font-semibold text-white px-4 py-2 rounded-lg
                      ${isDanger ? 'bg-red-600 hover:bg-red-700' : 'bg-indigo-600 hover:bg-indigo-700'}`}
                  >
                    {pending.confirmLabel || 'Confirm'}
                  </button>
                </div>
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </ConfirmContext.Provider>
  )
=======
import { useState, useCallback } from 'react';

interface ConfirmOptions {
  title: string;
  description: string;
  confirmLabel?: string;
  variant?: 'danger' | 'default';
}

export function useConfirm() {
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const [resolveRef, setResolveRef] = useState<((value: boolean) => void) | null>(null);

  const confirm = useCallback((opts: ConfirmOptions): Promise<boolean> => {
    setOptions(opts);
    setOpen(true);
    return new Promise((resolve) => {
      setResolveRef(() => resolve);
    });
  }, []);

  const handleConfirm = useCallback(() => {
    setOpen(false);
    resolveRef?.(true);
    setResolveRef(null);
  }, [resolveRef]);

  const handleCancel = useCallback(() => {
    setOpen(false);
    resolveRef?.(false);
    setResolveRef(null);
  }, [resolveRef]);

  const ConfirmDialog = useCallback(() => {
    if (!open || !options) return null;
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white rounded-lg p-6 max-w-sm w-full">
          <h3 className="text-lg font-semibold">{options.title}</h3>
          <p className="text-muted-foreground mt-2">{options.description}</p>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={handleCancel} className="px-4 py-2 rounded border">Cancel</button>
            <button
              onClick={handleConfirm}
              className={`px-4 py-2 rounded text-white ${options.variant === 'danger' ? 'bg-red-600' : 'bg-indigo-600'}`}
            >
              {options.confirmLabel || 'Confirm'}
            </button>
          </div>
        </div>
      </div>
    );
  }, [open, options, handleCancel, handleConfirm]);

  return { confirm, ConfirmDialog };
>>>>>>> origin/main
}

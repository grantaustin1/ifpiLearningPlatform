import React, { useState, useCallback } from 'react';

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

  const handleConfirm = () => {
    setOpen(false);
    resolveRef?.(true);
    setResolveRef(null);
  };

  const handleCancel = () => {
    setOpen(false);
    resolveRef?.(false);
    setResolveRef(null);
  };

  const ConfirmDialog = open && options ? (
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
  ) : null;

  return confirm;
}

import React, { useState, useCallback } from 'react';

interface PromptOptions {
  title: string;
  description: string;
  placeholder?: string;
  required?: boolean;
  maxLength?: number;
  confirmLabel?: string;
}

export function usePrompt() {
  const [value, setValue] = useState('');

  const prompt = useCallback((opts: PromptOptions): Promise<string | null> => {
    return new Promise((resolve) => {
      const result = window.prompt(`${opts.title}\n${opts.description}\n${opts.placeholder || ''}`);
      resolve(result);
    });
  }, []);

  return prompt;
}

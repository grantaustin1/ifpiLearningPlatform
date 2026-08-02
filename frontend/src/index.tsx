import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import App from './App'
import { AuthProvider } from './contexts/AuthContext'
<<<<<<< HEAD
import { ConfirmDialogProvider } from './components/ConfirmDialog'
import { PromptDialogProvider } from './components/PromptDialog'
=======
>>>>>>> origin/main
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
<<<<<<< HEAD
          <ConfirmDialogProvider>
            <PromptDialogProvider>
              <App />
              <Toaster position="bottom-right" richColors closeButton />
            </PromptDialogProvider>
          </ConfirmDialogProvider>
=======
          <App />
          <Toaster position="bottom-right" richColors closeButton />
>>>>>>> origin/main
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
)

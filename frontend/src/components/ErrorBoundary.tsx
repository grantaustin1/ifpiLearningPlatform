import React from 'react'
import { RefreshCw, TriangleAlert } from 'lucide-react'

interface State { error: Error | null }

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6" data-testid="error-boundary">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-8 max-w-md text-center">
            <div className="w-12 h-12 rounded-full bg-amber-50 flex items-center justify-center mx-auto mb-4">
              <TriangleAlert className="h-6 w-6 text-amber-500" />
            </div>
            <h1 className="text-lg font-semibold text-slate-800 mb-1">Something went wrong</h1>
            <p className="text-sm text-slate-500 mb-5">
              An unexpected error occurred on this page. Your data is safe — reloading usually fixes it.
            </p>
            <button
              onClick={() => { this.setState({ error: null }); window.location.reload() }}
              data-testid="error-boundary-reload"
              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-5 py-2.5 rounded-xl transition-colors">
              <RefreshCw className="h-4 w-4" /> Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

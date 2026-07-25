import { useEffect, useState, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { api } from 'lib/api'
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'


type Status = 'polling' | 'paid' | 'expired' | 'failed' | 'error'


interface StatusResp {
  session_id: string
  status: string
  payment_status: string | null
  amount_cents: number
  currency: string
  course_id: number
  entitled: boolean
  already_processed: boolean
}


const MAX_ATTEMPTS = 8
const POLL_INTERVAL_MS = 2000


export default function BillingSuccessPage() {
  const [params] = useSearchParams()
  const nav = useNavigate()
  const sessionId = params.get('session_id')
  const [status, setStatus] = useState<Status>('polling')
  const [attempt, setAttempt] = useState(0)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [details, setDetails] = useState<StatusResp | null>(null)
  const enrolledRef = useRef(false)

  useEffect(() => {
    if (!sessionId) {
      setStatus('error')
      setErrorMsg('Missing session_id in URL')
      return
    }

    let cancelled = false
    let timeoutId: ReturnType<typeof setTimeout> | null = null

    const poll = async (n: number) => {
      if (cancelled) return
      setAttempt(n)
      try {
        const r = await api.get(`/payments/v1/checkout/status/${sessionId}`)
        const data = r.data as StatusResp
        setDetails(data)

        if (data.entitled && data.payment_status === 'paid') {
          setStatus('paid')
          // Auto-enroll once (server-side is idempotent, but avoid
          // spamming the endpoint on re-renders).
          if (!enrolledRef.current) {
            enrolledRef.current = true
            try {
              await api.post(`/courses/${data.course_id}/enroll`)
            } catch {/* enrollment may 409 if already enrolled — fine */}
          }
          // Navigate to the course after a short beat so the user
          // sees the success state.
          timeoutId = setTimeout(() => nav(`/learn/${data.course_id}`), 1500)
          return
        }

        if (data.status === 'expired') {
          setStatus('expired'); return
        }

        // Not paid yet — try again if we have attempts left
        if (n + 1 >= MAX_ATTEMPTS) {
          setStatus('failed')
          return
        }
        timeoutId = setTimeout(() => poll(n + 1), POLL_INTERVAL_MS)
      } catch (e: any) {
        if (cancelled) return
        setStatus('error')
        setErrorMsg(e?.response?.data?.detail
          || e?.response?.data?.error?.message
          || 'Payment status check failed')
      }
    }

    poll(0)
    return () => {
      cancelled = true
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [sessionId, nav])


  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4"
      data-testid="billing-success-page">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-slate-200 p-8 text-center">
        {status === 'polling' && (
          <>
            <Loader2 className="h-12 w-12 text-indigo-600 mx-auto animate-spin" />
            <h1 className="mt-4 text-lg font-semibold text-slate-900">
              Confirming your payment…
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              This usually takes a few seconds. Attempt {attempt + 1} of {MAX_ATTEMPTS}.
            </p>
          </>
        )}

        {status === 'paid' && (
          <>
            <CheckCircle2 className="h-12 w-12 text-emerald-600 mx-auto"
              data-testid="billing-success-icon" />
            <h1 className="mt-4 text-lg font-semibold text-slate-900">
              Payment received!
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              You're enrolled in course #{details?.course_id}. Taking
              you to the classroom…
            </p>
          </>
        )}

        {status === 'expired' && (
          <>
            <XCircle className="h-12 w-12 text-slate-400 mx-auto" />
            <h1 className="mt-4 text-lg font-semibold text-slate-900">
              Checkout expired
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              This payment session timed out. Please try again.
            </p>
            <button onClick={() => nav('/catalog')}
              data-testid="billing-retry-btn"
              className="mt-6 inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
              Back to catalog
            </button>
          </>
        )}

        {status === 'failed' && (
          <>
            <XCircle className="h-12 w-12 text-amber-500 mx-auto" />
            <h1 className="mt-4 text-lg font-semibold text-slate-900">
              Waiting for confirmation
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              We didn't see the payment confirmed within a few seconds.
              Check your email for a receipt — access will unlock as
              soon as Stripe finalises.
            </p>
            <button onClick={() => nav('/billing')}
              className="mt-6 inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-900 text-white text-sm font-medium px-4 py-2 rounded-lg">
              View my subscriptions
            </button>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircle className="h-12 w-12 text-red-500 mx-auto" />
            <h1 className="mt-4 text-lg font-semibold text-slate-900">
              Something went wrong
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              {errorMsg || 'Unknown error while confirming your payment.'}
            </p>
            <button onClick={() => nav('/catalog')}
              className="mt-6 inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-900 text-white text-sm font-medium px-4 py-2 rounded-lg">
              Back to catalog
            </button>
          </>
        )}
      </div>
    </div>
  )
}

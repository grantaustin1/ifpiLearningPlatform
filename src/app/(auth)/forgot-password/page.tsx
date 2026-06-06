"use client"

import { useState } from "react"
import Link from "next/link"
import { GraduationCap, ArrowLeft, Mail } from "lucide-react"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // Mark as submitted – shows confirmation screen.
    // Wire up email sending here once SMTP is configured.
    setSubmitted(true)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-8">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-2 mb-8 justify-center">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
            <GraduationCap className="h-5 w-5 text-white" />
          </div>
          <span className="text-xl font-bold text-slate-900">IFPI Learning</span>
        </div>

        {!submitted ? (
          <>
            <div className="mb-8">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                Reset password
              </h1>
              <p className="text-slate-500 text-sm mt-1">
                Enter your email and we&apos;ll send you a reset link.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5 uppercase tracking-wide">
                  Email address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-10 pr-4 py-3 bg-white border border-slate-200 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-400 transition-all"
                    placeholder="you@example.com"
                    autoComplete="email"
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-xl shadow-lg shadow-indigo-200 hover:shadow-xl transition-all hover:-translate-y-0.5 mt-2"
              >
                Send reset link
              </button>
            </form>
          </>
        ) : (
          <div className="text-center">
            <div className="w-14 h-14 rounded-full bg-indigo-50 flex items-center justify-center mx-auto mb-4">
              <Mail className="h-7 w-7 text-indigo-500" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 mb-2">Check your email</h2>
            <p className="text-slate-500 text-sm">
              If an account exists for{" "}
              <strong className="text-slate-700">{email}</strong>, you&apos;ll
              receive a reset link shortly.
            </p>
          </div>
        )}

        <Link
          href="/login"
          className="flex items-center justify-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mt-6 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to sign in
        </Link>
      </div>
    </div>
  )
}

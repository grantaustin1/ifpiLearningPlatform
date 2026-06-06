"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import { Clock, CheckCircle, XCircle, ChevronLeft, ChevronRight, AlertCircle, Star } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

interface Question {
  id: string; text: string; questionType: string
  options?: string; points: number; order: number; category?: string
}
interface Exam {
  id: string; title: string; description?: string; instructions?: string
  passingScore: number; timeLimit?: number; maxAttempts: number; questions: Question[]
}
interface Result {
  score: number; passed: boolean; xpEarned: number; badgesEarned: string[]
}

export default function TakeExamPage() {
  const params = useParams()
  const router = useRouter()
  const [exam, setExam] = useState<Exam | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [current, setCurrent] = useState(0)
  const [phase, setPhase] = useState<"intro" | "taking" | "submitting" | "result">("intro")
  const [timeLeft, setTimeLeft] = useState<number | null>(null)
  const [startTime, setStartTime] = useState<number>(0)
  const [result, setResult] = useState<Result | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/exams/${params.examId}`)
      .then(r => r.json())
      .then(data => { setExam(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [params.examId])

  useEffect(() => {
    if (phase !== "taking" || !exam?.timeLimit) return
    setTimeLeft(exam.timeLimit * 60)
    setStartTime(Date.now())
  }, [phase, exam?.timeLimit])

  useEffect(() => {
    if (phase === "taking" && exam && !exam.timeLimit) setStartTime(Date.now())
  }, [phase])

  useEffect(() => {
    if (timeLeft === null || phase !== "taking") return
    if (timeLeft <= 0) { handleSubmit(); return }
    const t = setTimeout(() => setTimeLeft(tl => (tl ?? 1) - 1), 1000)
    return () => clearTimeout(t)
  }, [timeLeft, phase])

  const handleSubmit = useCallback(async () => {
    if (!exam) return
    setPhase("submitting")
    const timeTaken = startTime > 0 ? Math.round((Date.now() - startTime) / 1000) : undefined
    try {
      const res = await fetch(`/api/exams/${exam.id}/attempts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers, timeTaken }),
      })
      if (!res.ok) {
        const err = await res.json()
        alert(err.error ?? "Submission failed"); setPhase("taking"); return
      }
      setResult(await res.json())
      setPhase("result")
    } catch {
      alert("Network error. Please try again."); setPhase("taking")
    }
  }, [exam, answers, startTime])

  const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  )
  if (!exam) return <div className="min-h-screen flex items-center justify-center"><p className="text-gray-500">Exam not found.</p></div>

  if (phase === "intro") return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="max-w-lg w-full border-0 shadow-xl">
        <CardContent className="p-8">
          <div className="text-center mb-6">
            <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="h-8 w-8 text-indigo-600" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">{exam.title}</h1>
            {exam.description && <p className="text-gray-500 mt-2">{exam.description}</p>}
          </div>
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-gray-50 rounded-lg p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">{exam.questions.length}</p>
              <p className="text-sm text-gray-500">Questions</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">{exam.passingScore}%</p>
              <p className="text-sm text-gray-500">Pass mark</p>
            </div>
            {exam.timeLimit && (
              <div className="bg-gray-50 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-gray-900">{exam.timeLimit}m</p>
                <p className="text-sm text-gray-500">Time limit</p>
              </div>
            )}
            <div className="bg-gray-50 rounded-lg p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">{exam.maxAttempts}</p>
              <p className="text-sm text-gray-500">Max attempts</p>
            </div>
          </div>
          {exam.instructions && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
              <div className="flex gap-2">
                <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-amber-800">{exam.instructions}</p>
              </div>
            </div>
          )}
          <Button className="w-full bg-indigo-600 hover:bg-indigo-700" onClick={() => setPhase("taking")}>
            Start Exam
          </Button>
        </CardContent>
      </Card>
    </div>
  )

  if (phase === "result" && result) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="max-w-md w-full border-0 shadow-xl">
        <CardContent className="p-8 text-center">
          <div className={`w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 ${result.passed ? "bg-green-100" : "bg-red-100"}`}>
            {result.passed ? <CheckCircle className="h-10 w-10 text-green-600" /> : <XCircle className="h-10 w-10 text-red-600" />}
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">{result.passed ? "Congratulations!" : "Not quite"}</h2>
          <p className="text-gray-500 mb-4">{result.passed ? "You passed the exam." : `You need ${exam.passingScore}% to pass.`}</p>
          {result.xpEarned > 0 && (
            <div className="inline-flex items-center gap-1.5 bg-amber-50 border border-amber-200 text-amber-700 text-sm font-semibold px-3 py-1.5 rounded-full mb-4">
              <Star className="h-4 w-4" /> +{result.xpEarned} XP earned
            </div>
          )}
          {result.badgesEarned.length > 0 && (
            <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-3 mb-4">
              <p className="text-xs font-semibold text-indigo-700 mb-1">New badge{result.badgesEarned.length > 1 ? "s" : ""} unlocked!</p>
              <div className="flex gap-2 justify-center text-2xl">
                {result.badgesEarned.map(b => (
                  <span key={b} title={b}>{b === "EXAM_PASSER" ? "📚" : b === "PERFECT_SCORE" ? "💯" : "🏅"}</span>
                ))}
              </div>
            </div>
          )}
          <div className="w-32 h-32 relative mx-auto mb-6">
            <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" fill="none" stroke="#e5e7eb" strokeWidth="10" />
              <circle cx="50" cy="50" r="45" fill="none"
                stroke={result.passed ? "#16a34a" : "#dc2626"} strokeWidth="10"
                strokeDasharray={`${result.score * 2.83} 283`} strokeLinecap="round" />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-2xl font-bold text-gray-900">{result.score}%</span>
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" className="flex-1" onClick={() => router.push("/dashboard")}>Dashboard</Button>
            {!result.passed && (
              <Button className="flex-1 bg-indigo-600 hover:bg-indigo-700" onClick={() => { setPhase("intro"); setAnswers({}); setCurrent(0) }}>
                Retry
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )

  if (phase === "submitting") return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-gray-500">Grading your exam…</p>
      </div>
    </div>
  )

  const q = exam.questions[current]
  const opts: string[] = q?.options ? JSON.parse(q.options) : []
  const answered = Object.keys(answers).length

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <div className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <span className="font-semibold text-gray-900 truncate max-w-xs">{exam.title}</span>
        <div className="flex items-center gap-4">
          {timeLeft !== null && (
            <div className={`flex items-center gap-1.5 text-sm font-mono font-semibold ${timeLeft < 60 ? "text-red-600" : "text-gray-700"}`}>
              <Clock className="h-4 w-4" /> {fmt(timeLeft)}
            </div>
          )}
          <span className="text-sm text-gray-500">{answered}/{exam.questions.length} answered</span>
        </div>
      </div>
      <div className="h-1 bg-gray-100">
        <div className="h-1 bg-indigo-600 transition-all" style={{ width: `${((current + 1) / exam.questions.length) * 100}%` }} />
      </div>
      <div className="flex-1 flex items-center justify-center p-4">
        <Card className="max-w-2xl w-full border-0 shadow-lg">
          <CardContent className="p-8">
            <div className="flex items-start justify-between mb-6">
              <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full">
                Question {current + 1} of {exam.questions.length}
              </span>
              <span className="text-xs text-gray-400">{q?.points} pt{q?.points !== 1 ? "s" : ""}</span>
            </div>
            <h2 className="text-lg font-semibold text-gray-900 mb-6 leading-relaxed">{q?.text}</h2>
            {q?.questionType === "MULTIPLE_CHOICE" && (
              <div className="space-y-3">
                {opts.map((opt, i) => (
                  <button key={i}
                    onClick={() => setAnswers(a => ({ ...a, [q.id]: i.toString() }))}
                    className={`w-full text-left px-4 py-3 rounded-xl border-2 text-sm transition-all ${
                      answers[q.id] === i.toString()
                        ? "border-indigo-500 bg-indigo-50 text-indigo-700 font-medium"
                        : "border-gray-200 hover:border-gray-300 text-gray-700"
                    }`}
                  >
                    <span className="font-semibold mr-2">{String.fromCharCode(65 + i)}.</span>{opt}
                  </button>
                ))}
              </div>
            )}
            {q?.questionType === "TRUE_FALSE" && (
              <div className="flex gap-3">
                {["true", "false"].map(val => (
                  <button key={val}
                    onClick={() => setAnswers(a => ({ ...a, [q.id]: val }))}
                    className={`flex-1 py-3 rounded-xl border-2 text-sm font-medium transition-all ${
                      answers[q.id] === val
                        ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                        : "border-gray-200 hover:border-gray-300 text-gray-700"
                    }`}
                  >
                    {val === "true" ? "✅ True" : "❌ False"}
                  </button>
                ))}
              </div>
            )}
            {(q?.questionType === "FILL_IN_BLANK" || q?.questionType === "SHORT_ANSWER") && (
              <input type="text"
                value={answers[q.id] ?? ""}
                onChange={e => setAnswers(a => ({ ...a, [q.id]: e.target.value }))}
                placeholder="Type your answer…"
                className="w-full border-2 border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-indigo-400 transition-colors"
              />
            )}
          </CardContent>
        </Card>
      </div>
      <div className="bg-white border-t px-6 py-4 flex items-center justify-between">
        <Button variant="outline" onClick={() => setCurrent(Math.max(0, current - 1))} disabled={current === 0} className="gap-2">
          <ChevronLeft className="h-4 w-4" /> Previous
        </Button>
        {current < exam.questions.length - 1 ? (
          <Button className="bg-indigo-600 hover:bg-indigo-700 gap-2" onClick={() => setCurrent(current + 1)}>
            Next <ChevronRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button className="bg-emerald-600 hover:bg-emerald-700 gap-2" onClick={handleSubmit}>
            <CheckCircle className="h-4 w-4" /> Submit Exam
          </Button>
        )}
      </div>
    </div>
  )
}

"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import { useSession } from "next-auth/react"
import { Clock, CheckCircle, XCircle, ChevronLeft, ChevronRight, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

interface Option { text: string }
interface Question {
  id: string
  text: string
  questionType: string
  options?: string
  points: number
  order: number
  category?: string
}
interface Exam {
  id: string
  title: string
  description?: string
  instructions?: string
  passingScore: number
  timeLimit?: number
  maxAttempts: number
  questions: Question[]
}

export default function TakeExamPage() {
  const params = useParams()
  const router = useRouter()
  const { data: session } = useSession()
  const [exam, setExam] = useState<Exam | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [current, setCurrent] = useState(0)
  const [phase, setPhase] = useState<"intro" | "taking" | "submitting" | "result">("intro")
  const [timeLeft, setTimeLeft] = useState<number | null>(null)
  const [result, setResult] = useState<{ score: number; passed: boolean; total: number } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/exams/${params.examId}`)
      .then(r => r.json())
      .then(data => { setExam(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [params.examId])

  // Timer
  useEffect(() => {
    if (phase !== "taking" || !exam?.timeLimit) return
    setTimeLeft(exam.timeLimit * 60)
  }, [phase, exam?.timeLimit])

  useEffect(() => {
    if (timeLeft === null || phase !== "taking") return
    if (timeLeft <= 0) { handleSubmit(); return }
    const t = setTimeout(() => setTimeLeft(tl => (tl ?? 1) - 1), 1000)
    return () => clearTimeout(t)
  }, [timeLeft, phase])

  const handleSubmit = useCallback(async () => {
    if (!exam) return
    setPhase("submitting")

    // Grade locally
    let correct = 0
    let total = 0
    exam.questions.forEach(q => {
      const opts: string[] = q.options ? JSON.parse(q.options) : []
      const ans = answers[q.id] ?? ""
      total += q.points
      if (q.questionType === "MULTIPLE_CHOICE" || q.questionType === "TRUE_FALSE") {
        // correctAnswer stored as option index
        if (ans === q.questionType) correct += q.points // placeholder
      }
    })

    const score = total > 0 ? Math.round((correct / total) * 100) : 0
    const passed = score >= exam.passingScore

    setResult({ score, passed, total })
    setPhase("result")
  }, [exam, answers])

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, "0")}`
  }

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (!exam) return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-gray-500">Exam not found.</p>
    </div>
  )

  // Intro screen
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

  // Result screen
  if (phase === "result" && result) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="max-w-md w-full border-0 shadow-xl">
        <CardContent className="p-8 text-center">
          <div className={`w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 ${result.passed ? "bg-green-100" : "bg-red-100"}`}>
            {result.passed
              ? <CheckCircle className="h-10 w-10 text-green-600" />
              : <XCircle className="h-10 w-10 text-red-600" />}
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            {result.passed ? "Congratulations!" : "Not quite"}
          </h2>
          <p className="text-gray-500 mb-6">
            {result.passed ? "You passed the exam." : `You need ${exam.passingScore}% to pass.`}
          </p>

          <div className="w-32 h-32 relative mx-auto mb-6">
            <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" fill="none" stroke="#e5e7eb" strokeWidth="10" />
              <circle
                cx="50" cy="50" r="45" fill="none"
                stroke={result.passed ? "#16a34a" : "#dc2626"}
                strokeWidth="10"
                strokeDasharray={`${result.score * 2.83} 283`}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-2xl font-bold text-gray-900">{result.score}%</span>
            </div>
          </div>

          <div className="flex gap-3">
            <Button variant="outline" className="flex-1" onClick={() => router.push("/dashboard")}>
              Dashboard
            </Button>
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

  // Taking exam
  const q = exam.questions[current]
  const opts: string[] = q?.options ? JSON.parse(q.options) : []

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <span className="font-semibold text-gray-900 truncate max-w-xs">{exam.title}</span>
        <div className="flex items-center gap-4">
          {timeLeft !== null && (
            <div className={`flex items-center gap-1.5 text-sm font-medium ${timeLeft < 60 ? "text-red-600" : "text-gray-700"}`}>
              <Clock className="h-4 w-4" />
              {formatTime(timeLeft)}
            </div>
          )}
          <span className="text-sm text-gray-500">{current + 1} / {exam.questions.length}</span>
        </div>
      </div>

      {/* Progress */}
      <div className="h-1 bg-gray-100">
        <div
          className="h-1 bg-indigo-600 transition-all"
          style={{ width: `${((current + 1) / exam.questions.length) * 100}%` }}
        />
      </div>

      {/* Question */}
      <div className="flex-1 flex items-start justify-center pt-12 px-4 pb-24">
        <div className="w-full max-w-2xl">
          {q.category && (
            <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-1 rounded-full mb-4 inline-block">
              {q.category}
            </span>
          )}
          <h2 className="text-xl font-semibold text-gray-900 mb-8">{q.text}</h2>

          {(q.questionType === "MULTIPLE_CHOICE" || q.questionType === "TRUE_FALSE") && (
            <div className="space-y-3">
              {opts.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => setAnswers({ ...answers, [q.id]: String(i) })}
                  className={`w-full text-left px-4 py-4 rounded-xl border-2 transition-all ${
                    answers[q.id] === String(i)
                      ? "border-indigo-600 bg-indigo-50 text-indigo-900"
                      : "border-gray-200 hover:border-gray-300 bg-white"
                  }`}
                >
                  <span className="font-medium mr-3 text-gray-400">{String.fromCharCode(65 + i)}</span>
                  {opt}
                </button>
              ))}
            </div>
          )}

          {(q.questionType === "SHORT_ANSWER" || q.questionType === "FILL_IN_BLANK") && (
            <textarea
              value={answers[q.id] ?? ""}
              onChange={e => setAnswers({ ...answers, [q.id]: e.target.value })}
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-indigo-600 text-sm"
              rows={4}
              placeholder="Your answer..."
            />
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t px-6 py-4 flex items-center justify-between">
        <Button variant="outline" onClick={() => setCurrent(Math.max(0, current - 1))} disabled={current === 0} className="gap-2">
          <ChevronLeft className="h-4 w-4" /> Previous
        </Button>
        {current < exam.questions.length - 1 ? (
          <Button className="bg-indigo-600 hover:bg-indigo-700 gap-2" onClick={() => setCurrent(current + 1)}>
            Next <ChevronRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button className="bg-green-600 hover:bg-green-700 gap-2" onClick={handleSubmit}>
            <CheckCircle className="h-4 w-4" /> Submit Exam
          </Button>
        )}
      </div>
    </div>
  )
}

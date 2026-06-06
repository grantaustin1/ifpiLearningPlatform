"use client"

import { useState } from "react"
import Link from "next/link"
import { ArrowLeft, Plus, Trash2, GripVertical, Save, Settings, CheckSquare, Circle, AlignLeft, ToggleLeft, Image, Video } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

const questionTypes = [
  { type: "MULTIPLE_CHOICE", label: "Multiple Choice", icon: CheckSquare, desc: "One correct answer" },
  { type: "MULTIPLE_SELECT", label: "Multi-Select", icon: CheckSquare, desc: "Multiple correct answers" },
  { type: "TRUE_FALSE", label: "True / False", icon: ToggleLeft, desc: "Binary answer" },
  { type: "FILL_IN_BLANK", label: "Fill in the Blank", icon: AlignLeft, desc: "Text completion" },
  { type: "SHORT_ANSWER", label: "Short Answer", icon: AlignLeft, desc: "Free text response" },
  { type: "IMAGE_CHOICE", label: "Image Choice", icon: Image, desc: "Visual multiple choice" },
]

interface Question {
  id: string
  text: string
  type: string
  options: string[]
  correctAnswer: string
  points: number
  category: string
}

export default function NewExamPage() {
  const [title, setTitle] = useState("")
  const [questions, setQuestions] = useState<Question[]>([
    { id: "1", text: "", type: "MULTIPLE_CHOICE", options: ["", "", "", ""], correctAnswer: "0", points: 1, category: "" },
  ])
  const [activeQ, setActiveQ] = useState("1")
  const [settings, setSettings] = useState({
    passingScore: 70,
    timeLimit: 30,
    maxAttempts: 3,
    randomized: false,
    showResults: true,
  })

  const active = questions.find(q => q.id === activeQ)

  const addQuestion = (type: string) => {
    const q: Question = {
      id: Date.now().toString(),
      text: "",
      type,
      options: type === "TRUE_FALSE" ? ["True", "False"] : ["", "", "", ""],
      correctAnswer: "0",
      points: 1,
      category: "",
    }
    setQuestions([...questions, q])
    setActiveQ(q.id)
  }

  const updateQ = (id: string, updates: Partial<Question>) => {
    setQuestions(questions.map(q => q.id === id ? { ...q, ...updates } : q))
  }

  const updateOption = (qId: string, idx: number, value: string) => {
    const q = questions.find(q => q.id === qId)
    if (!q) return
    const newOptions = [...q.options]
    newOptions[idx] = value
    updateQ(qId, { options: newOptions })
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Top bar */}
      <div className="border-b bg-white px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/exams">
            <Button variant="ghost" size="sm" className="gap-2"><ArrowLeft className="h-4 w-4" /> Back</Button>
          </Link>
          <input
            className="text-lg font-semibold bg-transparent border-none focus:outline-none placeholder-gray-400"
            placeholder="Exam title..."
            value={title}
            onChange={e => setTitle(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">{questions.length} question{questions.length !== 1 ? "s" : ""}</span>
          <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700 gap-2">
            <Save className="h-4 w-4" /> Save & Publish
          </Button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Question list */}
        <div className="w-64 border-r bg-white flex flex-col overflow-hidden">
          <div className="p-4 border-b flex-1 overflow-y-auto">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Questions</p>
            <div className="space-y-1">
              {questions.map((q, idx) => (
                <div
                  key={q.id}
                  className={`flex items-start gap-2 p-2.5 rounded-lg cursor-pointer group ${activeQ === q.id ? "bg-indigo-50 border border-indigo-200" : "hover:bg-gray-50"}`}
                  onClick={() => setActiveQ(q.id)}
                >
                  <span className="text-xs text-gray-400 mt-0.5 w-4">{idx + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-700 truncate">{q.text || "New question"}</p>
                    <p className="text-xs text-gray-400">{q.type.replace("_", " ").toLowerCase()}</p>
                  </div>
                  <button className="opacity-0 group-hover:opacity-100" onClick={e => {
                    e.stopPropagation()
                    setQuestions(questions.filter(x => x.id !== q.id))
                    if (activeQ === q.id && questions.length > 1) setActiveQ(questions[0].id)
                  }}>
                    <Trash2 className="h-3 w-3 text-gray-400 hover:text-red-500" />
                  </button>
                </div>
              ))}
            </div>
          </div>
          <div className="p-4 border-t">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Add Question</p>
            <div className="space-y-1">
              {questionTypes.map(qt => (
                <button key={qt.type} onClick={() => addQuestion(qt.type)} className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-gray-50 text-left">
                  <qt.icon className="h-3.5 w-3.5 text-gray-500" />
                  <span className="text-sm text-gray-700">{qt.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Center: Question editor */}
        <div className="flex-1 overflow-y-auto bg-gray-50 p-8">
          {active && (
            <div className="max-w-2xl mx-auto space-y-6">
              <Card className="border-0 shadow-sm">
                <CardContent className="p-6 space-y-5">
                  {/* Question text */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Question</label>
                    <textarea
                      className="w-full border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                      rows={3}
                      placeholder="Enter your question here..."
                      value={active.text}
                      onChange={e => updateQ(active.id, { text: e.target.value })}
                    />
                  </div>

                  {/* Options */}
                  {(active.type === "MULTIPLE_CHOICE" || active.type === "MULTIPLE_SELECT") && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Answer Options</label>
                      <div className="space-y-2">
                        {active.options.map((opt, i) => (
                          <div key={i} className="flex items-center gap-3">
                            <input
                              type="radio"
                              name={`correct-${active.id}`}
                              checked={active.correctAnswer === String(i)}
                              onChange={() => updateQ(active.id, { correctAnswer: String(i) })}
                              className="w-4 h-4 text-indigo-600"
                            />
                            <input
                              className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              placeholder={`Option ${i + 1}`}
                              value={opt}
                              onChange={e => updateOption(active.id, i, e.target.value)}
                            />
                          </div>
                        ))}
                        <button
                          className="text-sm text-indigo-600 hover:underline flex items-center gap-1 mt-1"
                          onClick={() => updateQ(active.id, { options: [...active.options, ""] })}
                        >
                          <Plus className="h-3 w-3" /> Add option
                        </button>
                      </div>
                    </div>
                  )}

                  {active.type === "TRUE_FALSE" && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Correct Answer</label>
                      <div className="flex gap-4">
                        {["True", "False"].map(val => (
                          <label key={val} className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="radio"
                              name={`tf-${active.id}`}
                              checked={active.correctAnswer === val}
                              onChange={() => updateQ(active.id, { correctAnswer: val })}
                              className="w-4 h-4 text-indigo-600"
                            />
                            <span className="text-sm font-medium">{val}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  {(active.type === "FILL_IN_BLANK" || active.type === "SHORT_ANSWER") && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Model Answer</label>
                      <input
                        className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        placeholder="Enter the expected answer..."
                        value={active.correctAnswer}
                        onChange={e => updateQ(active.id, { correctAnswer: e.target.value })}
                      />
                    </div>
                  )}

                  {/* Category & Points */}
                  <div className="flex gap-4">
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Category (optional)</label>
                      <input
                        className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        placeholder="e.g. Copyright, Licensing..."
                        value={active.category}
                        onChange={e => updateQ(active.id, { category: e.target.value })}
                      />
                    </div>
                    <div className="w-24">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Points</label>
                      <input
                        type="number"
                        min={1}
                        className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        value={active.points}
                        onChange={e => updateQ(active.id, { points: parseInt(e.target.value) })}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>

        {/* Right: Exam settings */}
        <div className="w-72 border-l bg-white overflow-y-auto">
          <div className="p-6">
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Settings className="h-4 w-4" /> Exam Settings
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Passing Score (%)</label>
                <input
                  type="number" min={0} max={100}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  value={settings.passingScore}
                  onChange={e => setSettings({ ...settings, passingScore: +e.target.value })}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Time Limit (minutes)</label>
                <input
                  type="number" min={0}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="No limit"
                  value={settings.timeLimit}
                  onChange={e => setSettings({ ...settings, timeLimit: +e.target.value })}
                />
                <p className="text-xs text-gray-400 mt-1">Set to 0 for no time limit</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Max Attempts</label>
                <input
                  type="number" min={1}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  value={settings.maxAttempts}
                  onChange={e => setSettings({ ...settings, maxAttempts: +e.target.value })}
                />
              </div>
              <div className="space-y-3">
                <label className="flex items-center justify-between cursor-pointer">
                  <span className="text-sm text-gray-700">Randomize questions</span>
                  <input
                    type="checkbox"
                    checked={settings.randomized}
                    onChange={e => setSettings({ ...settings, randomized: e.target.checked })}
                    className="rounded"
                  />
                </label>
                <label className="flex items-center justify-between cursor-pointer">
                  <span className="text-sm text-gray-700">Show results after submission</span>
                  <input
                    type="checkbox"
                    checked={settings.showResults}
                    onChange={e => setSettings({ ...settings, showResults: e.target.checked })}
                    className="rounded"
                  />
                </label>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Award certificate on pass</label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" className="rounded" defaultChecked />
                  <span className="text-sm text-gray-600">Issue automatically</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

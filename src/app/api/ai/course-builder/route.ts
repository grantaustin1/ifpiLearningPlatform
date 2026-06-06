import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'

interface GeneratedSlide {
  title: string
  content: string
  slideType: 'TEXT'
  order: number
}

interface GeneratedQuestion {
  question: string
  questionType: 'MCQ'
  options: string[]
  correctAnswer: string
  explanation: string
  points: number
  order: number
}

interface AIBuilderResponse {
  slides: GeneratedSlide[]
  questions: GeneratedQuestion[]
}

export async function POST(req: NextRequest) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)
  if (!isAdmin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const apiKey = process.env.OPENAI_API_KEY
  if (!apiKey) {
    return NextResponse.json({ error: 'AI course builder requires OPENAI_API_KEY to be configured in environment variables.' }, { status: 503 })
  }

  const body = await req.json()
  const { topic, description = '', numSlides = 5, includeQuiz = true, numQuestions = 5 } = body

  if (!topic?.trim()) return NextResponse.json({ error: 'Topic is required' }, { status: 400 })
  if (numSlides < 1 || numSlides > 20) return NextResponse.json({ error: 'numSlides must be 1–20' }, { status: 400 })

  const quizSection = includeQuiz ? `
Also generate ${numQuestions} multiple-choice quiz questions to assess understanding of the topic.
Each question must have exactly 4 options (A, B, C, D), one correct answer, and a brief explanation.` : ''

  const systemPrompt = `You are an expert instructional designer. Generate clear, educational content in JSON format.
Only output valid JSON — no markdown, no prose, no code fences.`

  const userPrompt = `Create a course about: "${topic.trim()}"${description ? `

Additional context: ${description.trim()}` : ''}

Generate exactly ${numSlides} course slides. Each slide should be a self-contained lesson section.${quizSection}

Output this exact JSON structure (nothing else):
{
  "slides": [
    {
      "title": "slide title",
      "content": "HTML content for this slide (use <h2>, <p>, <ul>/<li>, <strong> for formatting — 150-300 words per slide)",
      "slideType": "TEXT",
      "order": 1
    }
  ]${includeQuiz ? `,
  "questions": [
    {
      "question": "question text",
      "questionType": "MCQ",
      "options": ["A) option1", "B) option2", "C) option3", "D) option4"],
      "correctAnswer": "A) option1",
      "explanation": "why this answer is correct",
      "points": 1,
      "order": 1
    }
  ]` : ''}
}`

  try {
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
        temperature: 0.7,
        max_tokens: 8000,
        response_format: { type: 'json_object' },
      }),
    })

    if (!response.ok) {
      const err = await response.json()
      console.error('OpenAI error:', err)
      return NextResponse.json({ error: `AI request failed: ${err.error?.message ?? response.status}` }, { status: 502 })
    }

    const data = await response.json()
    const raw = data.choices?.[0]?.message?.content ?? '{}'

    let parsed: AIBuilderResponse
    try {
      parsed = JSON.parse(raw)
    } catch {
      return NextResponse.json({ error: 'Failed to parse AI response. Please try again.' }, { status: 502 })
    }

    // Validate and normalise
    const slides: GeneratedSlide[] = (parsed.slides ?? []).map((s: any, i: number) => ({
      title: String(s.title ?? `Slide ${i + 1}`).trim(),
      content: String(s.content ?? '').trim(),
      slideType: 'TEXT' as const,
      order: i + 1,
    }))

    const questions: GeneratedQuestion[] = includeQuiz
      ? (parsed.questions ?? []).map((q: any, i: number) => ({
          question: String(q.question ?? '').trim(),
          questionType: 'MCQ' as const,
          options: Array.isArray(q.options) ? q.options.map(String) : [],
          correctAnswer: String(q.correctAnswer ?? '').trim(),
          explanation: String(q.explanation ?? '').trim(),
          points: Number(q.points ?? 1),
          order: i + 1,
        }))
      : []

    return NextResponse.json({ slides, questions })
  } catch (err) {
    console.error('AI builder error:', err)
    return NextResponse.json({ error: 'Network error contacting AI service. Please try again.' }, { status: 502 })
  }
}

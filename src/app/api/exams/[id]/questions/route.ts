import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/prisma"
import { auth } from "@/lib/auth"

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  const questions = await req.json()
  // Replace all questions
  await prisma.examQuestion.deleteMany({ where: { examId: params.id } })
  const created = await prisma.examQuestion.createMany({
    data: questions.map((q: any, i: number) => ({
      examId: params.id,
      text: q.text,
      questionType: q.type ?? "MULTIPLE_CHOICE",
      options: q.options ? JSON.stringify(q.options) : null,
      correctAnswer: q.correctAnswer,
      explanation: q.explanation,
      points: q.points ?? 1,
      category: q.category,
      order: i,
    })),
  })
  return NextResponse.json({ count: created.count })
}

import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/prisma"
import { auth } from "@/lib/auth"

export async function GET() {
  const session = await auth()
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })

  const exams = await prisma.exam.findMany({
    include: {
      _count: { select: { questions: true, attempts: true } },
      createdBy: { select: { name: true } },
    },
    orderBy: { createdAt: "desc" },
  })
  return NextResponse.json(exams)
}

export async function POST(req: NextRequest) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })

  const body = await req.json()
  const exam = await prisma.exam.create({
    data: {
      title: body.title,
      description: body.description,
      passingScore: body.passingScore ?? 70,
      timeLimit: body.timeLimit,
      maxAttempts: body.maxAttempts ?? 3,
      category: body.category,
      createdById: session!.user!.id as string,
    },
  })
  return NextResponse.json(exam)
}

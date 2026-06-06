import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/prisma"
import { auth } from "@/lib/auth"

export async function GET() {
  const session = await auth()
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })

  const courses = await prisma.course.findMany({
    include: {
      _count: { select: { slides: true, enrollments: true } },
      createdBy: { select: { name: true } },
    },
    orderBy: { createdAt: "desc" },
  })
  return NextResponse.json(courses)
}

export async function POST(req: NextRequest) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })

  const body = await req.json()
  const { title, description, category, passingScore, duration } = body

  const course = await prisma.course.create({
    data: {
      title,
      description,
      category,
      passingScore: passingScore ?? 70,
      duration,
      createdById: session!.user!.id as string,
    },
  })

  return NextResponse.json(course)
}

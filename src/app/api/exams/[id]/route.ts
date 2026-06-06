import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/prisma"
import { auth } from "@/lib/auth"

export async function GET(_: NextRequest, { params }: { params: { id: string } }) {
  const exam = await prisma.exam.findUnique({
    where: { id: params.id },
    include: {
      questions: { orderBy: { order: "asc" } },
      _count: { select: { attempts: true } },
    },
  })
  if (!exam) return NextResponse.json({ error: "Not found" }, { status: 404 })
  return NextResponse.json(exam)
}

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  const body = await req.json()
  const exam = await prisma.exam.update({ where: { id: params.id }, data: body })
  return NextResponse.json(exam)
}

export async function DELETE(_: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  await prisma.exam.delete({ where: { id: params.id } })
  return NextResponse.json({ success: true })
}

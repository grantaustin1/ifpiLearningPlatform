import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/prisma"
import { auth } from "@/lib/auth"

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  const body = await req.json()
  const count = await prisma.courseSlide.count({ where: { courseId: params.id } })
  const slide = await prisma.courseSlide.create({
    data: {
      courseId: params.id,
      title: body.title ?? `Slide ${count + 1}`,
      content: body.content ?? "",
      slideType: body.slideType ?? "TEXT",
      mediaUrl: body.mediaUrl,
      order: body.order ?? count + 1,
    },
  })
  return NextResponse.json(slide)
}

export async function PUT(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  const slides = await req.json() // full slide array for reorder
  await Promise.all(
    slides.map((s: any) =>
      prisma.courseSlide.update({ where: { id: s.id }, data: { order: s.order, title: s.title, content: s.content } })
    )
  )
  return NextResponse.json({ success: true })
}

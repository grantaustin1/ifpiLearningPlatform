import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const courseId = params.id
  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)

  const assignments = await prisma.assignment.findMany({
    where: { courseId, ...(isAdmin ? {} : { isPublished: true }) },
    orderBy: { createdAt: 'asc' },
    include: {
      _count: { select: { submissions: true } },
      submissions: isAdmin ? false : {
        where: { userId: session.user.id },
        select: { id: true, status: true, score: true, submittedAt: true },
      },
    },
  })

  return NextResponse.json({ assignments, isModerator: isAdmin })
}

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)
  if (!isAdmin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = await req.json()
  const { title, description, dueAt, maxScore = 100, isPublished = false } = body
  if (!title?.trim()) return NextResponse.json({ error: 'Title required' }, { status: 400 })

  const course = await prisma.course.findUnique({ where: { id: params.id }, select: { id: true } })
  if (!course) return NextResponse.json({ error: 'Course not found' }, { status: 404 })

  const assignment = await prisma.assignment.create({
    data: {
      courseId: params.id,
      createdById: session.user.id,
      title: title.trim(),
      description: description?.trim() ?? null,
      dueAt: dueAt ? new Date(dueAt) : null,
      maxScore: Number(maxScore),
      isPublished,
    },
  })

  return NextResponse.json(assignment, { status: 201 })
}

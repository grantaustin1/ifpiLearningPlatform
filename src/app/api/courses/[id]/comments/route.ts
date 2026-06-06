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
  const isAdmin = session.user.role === 'ADMIN' || session.user.role === 'SUPER_ADMIN'
  const isInstructor = session.user.role === 'INSTRUCTOR'
  const isModerator = isAdmin || isInstructor

  // Fetch top-level comments with their replies
  const raw = await prisma.courseComment.findMany({
    where: {
      courseId,
      parentId: null, // only top-level
    },
    include: {
      user: { select: { id: true, name: true, role: true } },
      replies: {
        where: { isDeleted: false },
        include: { user: { select: { id: true, name: true, role: true } } },
        orderBy: { createdAt: 'asc' },
      },
    },
    orderBy: [{ isPinned: 'desc' }, { createdAt: 'desc' }],
  })

  const totalVisible = await prisma.courseComment.count({
    where: { courseId, isDeleted: false },
  })

  const mapped = raw.map(c => ({
    id: c.id,
    content: c.isDeleted ? null : c.content,
    isPinned: c.isPinned,
    isDeleted: c.isDeleted,
    createdAt: c.createdAt,
    updatedAt: c.updatedAt,
    user: c.isDeleted ? null : c.user,
    isOwn: c.userId === session.user.id,
    isModerator,
    replies: c.replies.map(r => ({
      id: r.id,
      content: r.content,
      isPinned: false,
      isDeleted: false,
      createdAt: r.createdAt,
      updatedAt: r.updatedAt,
      user: r.user,
      isOwn: r.userId === session.user.id,
      isModerator,
      replies: [],
    })),
  }))

  return NextResponse.json({ comments: mapped, total: totalVisible, isModerator })
}

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const courseId = params.id
  const body = await req.json()
  const content = (body.content ?? '').trim()
  const parentId = body.parentId ?? null

  if (!content || content.length > 2000) {
    return NextResponse.json({ error: 'Content must be 1–2000 characters' }, { status: 400 })
  }

  // Verify course exists
  const course = await prisma.course.findUnique({ where: { id: courseId }, select: { id: true } })
  if (!course) return NextResponse.json({ error: 'Course not found' }, { status: 404 })

  // Verify parent exists if provided
  if (parentId) {
    const parent = await prisma.courseComment.findUnique({
      where: { id: parentId },
      select: { id: true, parentId: true },
    })
    if (!parent || parent.parentId !== null) {
      return NextResponse.json({ error: 'Invalid parent comment' }, { status: 400 })
    }
  }

  const comment = await prisma.courseComment.create({
    data: {
      content,
      courseId,
      userId: session.user.id,
      parentId,
    },
    include: { user: { select: { id: true, name: true, role: true } } },
  })

  return NextResponse.json({
    id: comment.id,
    content: comment.content,
    isPinned: comment.isPinned,
    isDeleted: false,
    createdAt: comment.createdAt,
    updatedAt: comment.updatedAt,
    user: comment.user,
    isOwn: true,
    replies: [],
  }, { status: 201 })
}

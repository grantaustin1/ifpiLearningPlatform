import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const comment = await prisma.courseComment.findUnique({
    where: { id: params.id },
    select: { id: true, userId: true, isDeleted: true },
  })
  if (!comment || comment.isDeleted) {
    return NextResponse.json({ error: 'Comment not found' }, { status: 404 })
  }

  const isAdmin = session.user.role === 'ADMIN' || session.user.role === 'SUPER_ADMIN'
  const isInstructor = session.user.role === 'INSTRUCTOR'
  const isOwn = comment.userId === session.user.id

  const body = await req.json()

  // Edit content — own comments only
  if (body.content !== undefined) {
    if (!isOwn) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
    const content = body.content.trim()
    if (!content || content.length > 2000) {
      return NextResponse.json({ error: 'Content must be 1–2000 characters' }, { status: 400 })
    }
    const updated = await prisma.courseComment.update({
      where: { id: params.id },
      data: { content },
    })
    return NextResponse.json({ id: updated.id, content: updated.content, updatedAt: updated.updatedAt })
  }

  // Toggle pin — moderators only
  if (body.isPinned !== undefined) {
    if (!isAdmin && !isInstructor) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
    const updated = await prisma.courseComment.update({
      where: { id: params.id },
      data: { isPinned: Boolean(body.isPinned) },
    })
    return NextResponse.json({ id: updated.id, isPinned: updated.isPinned })
  }

  return NextResponse.json({ error: 'Nothing to update' }, { status: 400 })
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const comment = await prisma.courseComment.findUnique({
    where: { id: params.id },
    select: { id: true, userId: true, isDeleted: true },
  })
  if (!comment || comment.isDeleted) {
    return NextResponse.json({ error: 'Comment not found' }, { status: 404 })
  }

  const isAdmin = session.user.role === 'ADMIN' || session.user.role === 'SUPER_ADMIN'
  const isInstructor = session.user.role === 'INSTRUCTOR'
  const isOwn = comment.userId === session.user.id

  if (!isOwn && !isAdmin && !isInstructor) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  // Soft delete
  await prisma.courseComment.update({
    where: { id: params.id },
    data: { isDeleted: true, isPinned: false },
  })

  return NextResponse.json({ success: true })
}

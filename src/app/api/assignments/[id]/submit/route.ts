import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const assignment = await prisma.assignment.findUnique({
    where: { id: params.id },
    select: { id: true, isPublished: true, dueAt: true },
  })
  if (!assignment) return NextResponse.json({ error: 'Assignment not found' }, { status: 404 })
  if (!assignment.isPublished) return NextResponse.json({ error: 'Assignment not available' }, { status: 403 })
  if (assignment.dueAt && new Date() > assignment.dueAt) {
    return NextResponse.json({ error: 'Submission deadline has passed' }, { status: 400 })
  }

  const existing = await prisma.assignmentSubmission.findUnique({
    where: { assignmentId_userId: { assignmentId: params.id, userId: session.user.id } },
    select: { id: true, status: true },
  })
  if (existing && existing.status !== 'RETURNED') {
    return NextResponse.json({ error: 'Already submitted' }, { status: 409 })
  }

  const body = await req.json()
  const content = body.content?.trim() ?? null
  const fileUrl = body.fileUrl?.trim() ?? null
  const fileName = body.fileName?.trim() ?? null

  if (!content && !fileUrl) {
    return NextResponse.json({ error: 'Please provide text content or a file link' }, { status: 400 })
  }

  const submission = await prisma.assignmentSubmission.upsert({
    where: { assignmentId_userId: { assignmentId: params.id, userId: session.user.id } },
    create: { assignmentId: params.id, userId: session.user.id, content, fileUrl, fileName, status: 'SUBMITTED' },
    update: { content, fileUrl, fileName, status: 'SUBMITTED', score: null, feedback: null, gradedAt: null, submittedAt: new Date() },
  })

  return NextResponse.json(submission, { status: 201 })
}

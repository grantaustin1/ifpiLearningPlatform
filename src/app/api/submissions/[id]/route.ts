import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)
  if (!isAdmin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const submission = await prisma.assignmentSubmission.findUnique({
    where: { id: params.id },
    include: { assignment: { select: { maxScore: true } } },
  })
  if (!submission) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  const body = await req.json()
  const score = body.score !== undefined ? Number(body.score) : undefined
  const feedback = body.feedback?.trim() ?? undefined
  const status = body.status ?? 'GRADED'

  if (score !== undefined && (isNaN(score) || score < 0 || score > submission.assignment.maxScore)) {
    return NextResponse.json({ error: `Score must be 0–${submission.assignment.maxScore}` }, { status: 400 })
  }

  const updated = await prisma.assignmentSubmission.update({
    where: { id: params.id },
    data: {
      ...(score !== undefined ? { score } : {}),
      ...(feedback !== undefined ? { feedback } : {}),
      status,
      gradedAt: new Date(),
    },
    include: { user: { select: { id: true, name: true, email: true } } },
  })

  return NextResponse.json(updated)
}

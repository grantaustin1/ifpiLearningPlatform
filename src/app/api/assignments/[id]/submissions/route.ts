import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)
  if (!isAdmin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const assignment = await prisma.assignment.findUnique({
    where: { id: params.id },
    select: { id: true, title: true, maxScore: true, courseId: true },
  })
  if (!assignment) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  const submissions = await prisma.assignmentSubmission.findMany({
    where: { assignmentId: params.id },
    include: { user: { select: { id: true, name: true, email: true } } },
    orderBy: { submittedAt: 'desc' },
  })

  return NextResponse.json({ assignment, submissions })
}

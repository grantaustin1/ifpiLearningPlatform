import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function GET() {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  const learners = await prisma.user.findMany({
    where: { role: 'LEARNER' },
    select: {
      id: true, name: true, points: true,
      badges: { select: { badge: true, earnedAt: true } },
      _count: {
        select: {
          enrollments: { where: { status: 'COMPLETED' } },
          certificates: true,
        },
      },
    },
    orderBy: { points: 'desc' },
    take: 50,
  })
  return NextResponse.json(learners)
}

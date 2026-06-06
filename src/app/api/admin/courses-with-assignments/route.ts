import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function GET() {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)
  if (!isAdmin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const courses = await prisma.course.findMany({
    where: { assignments: { some: {} } },
    select: {
      id: true,
      title: true,
      assignments: {
        select: { id: true, title: true, _count: { select: { submissions: true } } },
        orderBy: { createdAt: 'asc' },
      },
    },
    orderBy: { title: 'asc' },
  })

  return NextResponse.json(courses)
}

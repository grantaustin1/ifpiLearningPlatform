import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function GET() {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)

  const courses = await prisma.course.findMany({
    where: isAdmin ? {} : { isPublished: true },
    select: {
      id: true,
      title: true,
      category: true,
      coverColor: true,
      isPublished: true,
      duration: true,
      createdAt: true,
      _count: { select: { slides: true, enrollments: true } },
    },
    orderBy: { createdAt: 'desc' },
  })

  return NextResponse.json(courses)
}

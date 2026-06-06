import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function GET() {
  const session = await auth()
  if (!session || session.user.role !== 'ADMIN') {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const users = await prisma.user.findMany({
    orderBy: { createdAt: 'desc' },
    select: {
      id: true, name: true, email: true, role: true, points: true, createdAt: true,
      _count: {
        select: {
          enrollments: true,
          certificates: true,
        },
      },
      enrollments: {
        where: { status: 'COMPLETED' },
        select: { id: true },
      },
    },
  })

  return NextResponse.json(users.map(u => ({
    id: u.id,
    name: u.name,
    email: u.email,
    role: u.role,
    points: u.points,
    createdAt: u.createdAt,
    enrollments: u._count.enrollments,
    completed: u.enrollments.length,
    certificates: u._count.certificates,
  })))
}

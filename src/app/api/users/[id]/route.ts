import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function GET(_: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)
  const isSelf = session.user.id === params.id

  const user = await prisma.user.findUnique({
    where: { id: params.id },
    include: {
      badges: { orderBy: { earnedAt: 'desc' } },
      enrollments: {
        include: { course: { select: { id: true, title: true, coverColor: true } } },
        orderBy: { enrolledAt: 'desc' },
      },
      examAttempts: {
        include: { exam: { select: { id: true, title: true } } },
        orderBy: { startedAt: 'desc' },
        take: 30,
      },
      certificates: {
        include: {
          course: { select: { id: true, title: true } },
          exam: { select: { id: true, title: true } },
        },
        orderBy: { issuedAt: 'desc' },
      },
    },
  })

  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  // Learners can only see a limited public profile of other users
  if (!isAdmin && !isSelf) {
    return NextResponse.json({
      id: user.id,
      name: user.name,
      image: user.image,
      points: user.points,
      badges: user.badges,
      _count: {
        enrollments: user.enrollments.length,
        certificates: user.certificates.length,
      },
    })
  }

  // Admin / self: full profile (strip password)
  const { password, ...safe } = user as any
  return NextResponse.json({ ...safe, _count: { enrollments: user.enrollments.length, certificates: user.certificates.length } })
}

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const isAdmin = ['ADMIN', 'SUPER_ADMIN'].includes(session.user.role)
  if (!isAdmin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const { role } = await req.json()
  const updated = await prisma.user.update({
    where: { id: params.id },
    data: { ...(role ? { role } : {}) },
    select: { id: true, name: true, email: true, role: true, points: true },
  })
  return NextResponse.json(updated)
}

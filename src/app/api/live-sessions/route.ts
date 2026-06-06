import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function GET(req: NextRequest) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const upcoming = req.nextUrl.searchParams.get('upcoming') === 'true'
  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)

  const sessions = await prisma.liveSession.findMany({
    where: {
      ...(isAdmin ? {} : { isPublished: true }),
      ...(upcoming ? { scheduledAt: { gte: new Date() } } : {}),
    },
    include: {
      course: { select: { id: true, title: true } },
      createdBy: { select: { name: true } },
    },
    orderBy: { scheduledAt: 'asc' },
    take: 50,
  })

  return NextResponse.json({ sessions, isModerator: isAdmin })
}

export async function POST(req: NextRequest) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)
  if (!isAdmin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = await req.json()
  const { title, description, scheduledAt, durationMins = 60, meetingUrl, platform = 'zoom', maxCapacity, isPublished = false, courseId } = body

  if (!title?.trim()) return NextResponse.json({ error: 'Title required' }, { status: 400 })
  if (!scheduledAt) return NextResponse.json({ error: 'scheduledAt required' }, { status: 400 })

  const created = await prisma.liveSession.create({
    data: {
      title: title.trim(),
      description: description?.trim() ?? null,
      scheduledAt: new Date(scheduledAt),
      durationMins: Number(durationMins),
      meetingUrl: meetingUrl?.trim() ?? null,
      platform,
      maxCapacity: maxCapacity ? Number(maxCapacity) : null,
      isPublished,
      courseId: courseId ?? null,
      createdById: session.user.id,
    },
    include: {
      course: { select: { id: true, title: true } },
      createdBy: { select: { name: true } },
    },
  })

  return NextResponse.json(created, { status: 201 })
}

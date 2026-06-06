import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { awardXP, awardBadge, createNotification, XP } from '@/lib/gamification'

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const userId = session.user.id as string
  const courseId = params.id

  const course = await prisma.course.findUnique({
    where: { id: courseId }, select: { id: true, title: true },
  })
  if (!course) return NextResponse.json({ error: 'Course not found' }, { status: 404 })

  const existing = await prisma.enrollment.findUnique({
    where: { userId_courseId: { userId, courseId } }, select: { status: true },
  })
  const alreadyCompleted = existing?.status === 'COMPLETED'

  await prisma.enrollment.upsert({
    where: { userId_courseId: { userId, courseId } },
    update: { status: 'COMPLETED', progress: 100, completedAt: new Date() },
    create: { userId, courseId, status: 'COMPLETED', progress: 100, completedAt: new Date() },
  })

  const hasCert = await prisma.certificate.findFirst({ where: { userId, courseId } })
  if (!hasCert) {
    await prisma.certificate.create({ data: { userId, courseId, type: 'COURSE_COMPLETION' } })
  }

  if (alreadyCompleted) {
    return NextResponse.json({ success: true, xpEarned: 0, badgesEarned: [], alreadyCompleted: true })
  }

  await awardXP(userId, XP.COURSE_COMPLETE)
  await createNotification(userId, 'COURSE_COMPLETE',
    `\u{1F393} Completed: ${course.title}`,
    `You earned ${XP.COURSE_COMPLETE} XP and a certificate!`, '/certificates')

  const badgesEarned: string[] = []
  const completedCount = await prisma.enrollment.count({ where: { userId, status: 'COMPLETED' } })
  if (completedCount === 1 && await awardBadge(userId, 'FIRST_COURSE')) badgesEarned.push('FIRST_COURSE')
  if (completedCount >= 5 && await awardBadge(userId, 'COURSE_MASTER')) badgesEarned.push('COURSE_MASTER')

  return NextResponse.json({ success: true, xpEarned: XP.COURSE_COMPLETE, badgesEarned })
}

import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { BADGE_META } from '@/lib/gamification'

export async function GET() {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  const userId = session.user.id as string

  const [user, totalLearners] = await Promise.all([
    prisma.user.findUnique({
      where: { id: userId },
      select: {
        points: true,
        badges: { select: { badge: true, earnedAt: true }, orderBy: { earnedAt: 'asc' } },
      },
    }),
    prisma.user.count({ where: { role: 'LEARNER' } }),
  ])
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  const rank = (await prisma.user.count({
    where: { role: 'LEARNER', points: { gt: user.points } },
  })) + 1

  const badges = user.badges.map(b => ({
    badge: b.badge, earnedAt: b.earnedAt,
    meta: BADGE_META[b.badge] ?? { label: b.badge, emoji: '\u{1F3C5}', desc: '' },
  }))

  return NextResponse.json({ points: user.points, badges, rank, totalLearners })
}

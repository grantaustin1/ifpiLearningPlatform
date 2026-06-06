import { prisma } from './prisma'

export const XP = {
  FIRST_ENROLLMENT: 10,
  COURSE_COMPLETE: 50,
  EXAM_PASS: 100,
  PERFECT_SCORE_BONUS: 50,
} as const

export const BADGE_META: Record<string, { label: string; emoji: string; desc: string }> = {
  FIRST_ENROLLMENT: { label: 'First Step',    emoji: '\u{1F3AF}', desc: 'Enrolled in your first course' },
  FIRST_COURSE:     { label: 'Graduate',      emoji: '\u{1F393}', desc: 'Completed your first course'  },
  EXAM_PASSER:      { label: 'Scholar',       emoji: '\u{1F4DA}', desc: 'Passed your first exam'        },
  PERFECT_SCORE:    { label: 'Perfectionist', emoji: '\u{1F4AF}', desc: 'Scored 100% on an exam'        },
  COURSE_MASTER:    { label: 'Course Master', emoji: '\u{1F3C6}', desc: 'Completed 5 courses'           },
}

export async function awardXP(userId: string, amount: number): Promise<number> {
  const user = await prisma.user.update({
    where: { id: userId },
    data: { points: { increment: amount } },
    select: { points: true },
  })
  return user.points
}

export async function awardBadge(userId: string, badge: string): Promise<boolean> {
  try {
    await prisma.userBadge.create({ data: { userId, badge } })
    const meta = BADGE_META[badge]
    if (meta) {
      await createNotification(
        userId, 'BADGE_EARNED',
        `${meta.emoji} Badge earned: ${meta.label}`,
        meta.desc, '/profile',
      )
    }
    return true
  } catch {
    return false
  }
}

export async function createNotification(
  userId: string, type: string,
  title: string, message: string, link?: string,
) {
  return prisma.notification.create({
    data: { userId, type, title, message, link },
  })
}

import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { awardXP, awardBadge, createNotification, XP } from '@/lib/gamification'

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { answers } = await req.json() as {
    answers: Record<string, string>
  }

  const examId = params.id
  const userId = session.user.id as string

  const exam = await prisma.exam.findUnique({
    where: { id: examId },
    include: { questions: { orderBy: { order: 'asc' } } },
  })
  if (!exam) return NextResponse.json({ error: 'Exam not found' }, { status: 404 })

  const attemptCount = await prisma.examAttempt.count({ where: { examId, userId } })
  if (attemptCount >= exam.maxAttempts) {
    return NextResponse.json({ error: 'Maximum attempts reached' }, { status: 400 })
  }

  let earned = 0
  let totalPoints = 0
  const answerRecords: Array<{
    questionId: string; answer: string
  }> = []

  for (const q of exam.questions) {
    totalPoints += q.points
    const userAnswer = (answers[q.id] ?? '').toString().trim()
    let isCorrect = false
    if (q.correctAnswer != null) {
      isCorrect = userAnswer.toLowerCase() === q.correctAnswer.toString().trim().toLowerCase()
    }
    if (isCorrect) earned += q.points
    answerRecords.push({ questionId: q.id, answer: userAnswer })
  }

  const score = totalPoints > 0 ? Math.round((earned / totalPoints) * 100) : 0
  const passed = score >= exam.passingScore

  const attempt = await prisma.examAttempt.create({
    data: {
      examId, userId, score, passed,
      completedAt: new Date(),
      answers: { create: answerRecords },
    },
    select: { id: true },
  })

  let xpEarned = 0
  const badgesEarned: string[] = []
  try {
    if (passed) {
      xpEarned += XP.EXAM_PASS
      if (score === 100) xpEarned += XP.PERFECT_SCORE_BONUS
      await awardXP(userId, xpEarned)
      await createNotification(userId, 'EXAM_RESULT',
        `\u2705 Passed: ${exam.title}`,
        `You scored ${score}% and earned ${xpEarned} XP!`, '/exams')
      const passCount = await prisma.examAttempt.count({ where: { userId, passed: true } })
      if (passCount === 1 && await awardBadge(userId, 'EXAM_PASSER')) badgesEarned.push('EXAM_PASSER')
      if (score === 100 && await awardBadge(userId, 'PERFECT_SCORE')) badgesEarned.push('PERFECT_SCORE')
    } else {
      await createNotification(userId, 'EXAM_RESULT',
        `\u274C ${exam.title} \u2014 keep trying`,
        `You scored ${score}%. Pass mark is ${exam.passingScore}%.`, '/exams')
    }
  } catch (e) { console.error('Gamification error:', e) }

  return NextResponse.json({ score, passed, xpEarned, badgesEarned, attemptId: attempt.id })
}

import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function GET() {
  const session = await auth()
  if (!session || session.user.role !== 'ADMIN') {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const now = new Date()
  const sixMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 5, 1)

  const [
    userCounts,
    courseCount,
    enrollmentStats,
    examStats,
    certCount,
    monthlyRaw,
    topCourses,
    recentActivity,
  ] = await Promise.all([
    prisma.user.groupBy({ by: ['role'], _count: { id: true } }),
    prisma.course.count(),
    prisma.enrollment.groupBy({ by: ['status'], _count: { id: true } }),
    prisma.examAttempt.aggregate({ _avg: { score: true }, _count: { id: true } }),
    prisma.certificate.count(),

    // Monthly enrollments — last 6 months
    prisma.$queryRaw<Array<{ month: Date; count: bigint }>>`
      SELECT DATE_TRUNC('month', "enrolledAt") AS month, COUNT(*) AS count
      FROM "Enrollment"
      WHERE "enrolledAt" >= ${sixMonthsAgo}
      GROUP BY 1
      ORDER BY 1 ASC
    `,

    // Top 8 courses by enrollment count + completion
    prisma.course.findMany({
      select: {
        id: true, title: true,
        _count: { select: { enrollments: true } },
        enrollments: { where: { status: 'COMPLETED' }, select: { id: true } },
      },
      orderBy: { enrollments: { _count: 'desc' } },
      take: 8,
    }),

    // Last 8 enrollments
    prisma.enrollment.findMany({
      orderBy: { enrolledAt: 'desc' },
      take: 8,
      select: {
        status: true, enrolledAt: true, progress: true,
        user: { select: { name: true } },
        course: { select: { title: true } },
      },
    }),
  ])

  const totalLearners = userCounts.find(u => u.role === 'LEARNER')?._count.id ?? 0
  const totalEnrollments = enrollmentStats.reduce((s, e) => s + e._count.id, 0)
  const completedEnrollments = enrollmentStats.find(e => e.status === 'COMPLETED')?._count.id ?? 0

  return NextResponse.json({
    overview: {
      totalLearners,
      totalInstructors: userCounts.find(u => u.role === 'INSTRUCTOR')?._count.id ?? 0,
      totalAdmins: userCounts.find(u => u.role === 'ADMIN')?._count.id ?? 0,
      totalCourses: courseCount,
      totalEnrollments,
      completionRate: totalEnrollments > 0 ? Math.round((completedEnrollments / totalEnrollments) * 100) : 0,
      avgExamScore: Math.round(examStats._avg.score ?? 0),
      totalExamAttempts: examStats._count.id,
      totalCertificates: certCount,
    },
    monthlyEnrollments: monthlyRaw.map(r => ({
      month: r.month,
      count: Number(r.count),
    })),
    topCourses: topCourses.map(c => ({
      id: c.id,
      title: c.title,
      total: c._count.enrollments,
      completed: c.enrollments.length,
      rate: c._count.enrollments > 0
        ? Math.round((c.enrollments.length / c._count.enrollments) * 100)
        : 0,
    })),
    recentActivity: recentActivity.map(r => ({
      userName: r.user.name ?? 'Unknown',
      courseTitle: r.course.title,
      status: r.status,
      progress: r.progress,
      enrolledAt: r.enrolledAt,
    })),
  })
}

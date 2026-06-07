import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const q = searchParams.get('q')?.trim() ?? ''
  const category = searchParams.get('category')?.trim() ?? ''

  const courses = await prisma.course.findMany({
    where: {
      isPublished: true,
      ...(q ? { title: { contains: q, mode: 'insensitive' } } : {}),
      ...(category ? { category: { equals: category, mode: 'insensitive' } } : {}),
    },
    select: {
      id: true,
      title: true,
      description: true,
      category: true,
      coverColor: true,
      duration: true,
      createdAt: true,
      _count: { select: { slides: true, enrollments: true } },
    },
    // BUG-008 fix: correct Prisma syntax for ordering by relation count
    orderBy: [{ enrollments: { _count: 'desc' } }, { createdAt: 'desc' }],
    take: 100,
  })

  const categories = await prisma.course.findMany({
    where: { isPublished: true, category: { not: null } },
    select: { category: true },
    distinct: ['category'],
  })

  return NextResponse.json({
    courses,
    categories: categories.map(c => c.category).filter(Boolean),
  })
}

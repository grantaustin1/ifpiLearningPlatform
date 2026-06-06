import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function GET() {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  const notifications = await prisma.notification.findMany({
    where: { userId: session.user.id as string },
    orderBy: { createdAt: 'desc' },
    take: 25,
  })
  const unreadCount = notifications.filter(n => !n.isRead).length
  return NextResponse.json({ notifications, unreadCount })
}

export async function PATCH() {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  await prisma.notification.updateMany({
    where: { userId: session.user.id as string, isRead: false },
    data: { isRead: true },
  })
  return NextResponse.json({ success: true })
}

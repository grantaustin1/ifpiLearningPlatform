import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)
  if (!isAdmin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = await req.json()
  const updated = await prisma.liveSession.update({
    where: { id: params.id },
    data: {
      ...(body.title ? { title: body.title.trim() } : {}),
      ...(body.description !== undefined ? { description: body.description?.trim() ?? null } : {}),
      ...(body.scheduledAt ? { scheduledAt: new Date(body.scheduledAt) } : {}),
      ...(body.durationMins !== undefined ? { durationMins: Number(body.durationMins) } : {}),
      ...(body.meetingUrl !== undefined ? { meetingUrl: body.meetingUrl?.trim() ?? null } : {}),
      ...(body.platform ? { platform: body.platform } : {}),
      ...(body.isPublished !== undefined ? { isPublished: Boolean(body.isPublished) } : {}),
      ...(body.recordingUrl !== undefined ? { recordingUrl: body.recordingUrl?.trim() ?? null } : {}),
    },
  })
  return NextResponse.json(updated)
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth()
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const isAdmin = ['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].includes(session.user.role)
  if (!isAdmin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  await prisma.liveSession.delete({ where: { id: params.id } })
  return NextResponse.json({ success: true })
}

import { auth } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import bcrypt from "bcryptjs"
import { NextResponse } from "next/server"

export async function PATCH(req: Request) {
  const session = await auth()
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const body = await req.json()

  // ── Update display name ──────────────────────────────────
  if (body.name !== undefined) {
    if (!String(body.name).trim()) {
      return NextResponse.json({ error: "Name cannot be empty" }, { status: 400 })
    }
    await prisma.user.update({
      where: { id: session.user.id },
      data:  { name: String(body.name).trim() },
    })
    return NextResponse.json({ ok: true })
  }

  // ── Change password ──────────────────────────────────────
  if (body.currentPassword && body.newPassword) {
    if (String(body.newPassword).length < 8) {
      return NextResponse.json(
        { error: "New password must be at least 8 characters" },
        { status: 400 }
      )
    }

    const user = await prisma.user.findUnique({ where: { id: session.user.id } })
    if (!user?.password) {
      return NextResponse.json(
        { error: "No password set on this account" },
        { status: 400 }
      )
    }

    const match = await bcrypt.compare(String(body.currentPassword), user.password)
    if (!match) {
      return NextResponse.json(
        { error: "Current password is incorrect" },
        { status: 400 }
      )
    }

    const hashed = await bcrypt.hash(String(body.newPassword), 12)
    await prisma.user.update({
      where: { id: session.user.id },
      data:  { password: hashed },
    })
    return NextResponse.json({ ok: true })
  }

  return NextResponse.json({ error: "Nothing to update" }, { status: 400 })
}

import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import bcrypt from 'bcryptjs'

const VALID_ROLES = ['ADMIN', 'INSTRUCTOR', 'LEARNER'] as const
type Role = typeof VALID_ROLES[number]

function parseCSV(text: string): Record<string, string>[] {
  const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n').filter(l => l.trim())
  if (lines.length < 2) return []
  const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/['"]/g, ''))
  return lines.slice(1).map(line => {
    const vals = line.split(',').map(v => v.trim().replace(/^["']|["']$/g, ''))
    const obj: Record<string, string> = {}
    headers.forEach((h, i) => { obj[h] = vals[i] ?? '' })
    return obj
  })
}

export async function POST(req: NextRequest) {
  const session = await auth()
  if (!session || session.user.role !== 'ADMIN') {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const formData = await req.formData()
  const file = formData.get('file') as File | null
  if (!file) return NextResponse.json({ error: 'No file provided' }, { status: 400 })

  const text = await file.text()
  const rows = parseCSV(text)

  if (rows.length === 0) {
    return NextResponse.json({ error: 'CSV is empty or has no data rows' }, { status: 400 })
  }

  const results = { imported: 0, skipped: 0, errors: [] as string[] }

  for (const [i, row] of rows.entries()) {
    const lineNum = i + 2
    const name = row['name'] ?? row['full name'] ?? row['fullname'] ?? ''
    const email = (row['email'] ?? '').toLowerCase().trim()
    const password = row['password'] ?? ''
    const roleRaw = (row['role'] ?? 'LEARNER').toUpperCase().trim()

    if (!email || !email.includes('@')) {
      results.errors.push(`Row ${lineNum}: invalid email "${email}"`)
      continue
    }
    if (!name) {
      results.errors.push(`Row ${lineNum}: missing name`)
      continue
    }
    if (!password || password.length < 6) {
      results.errors.push(`Row ${lineNum}: password must be at least 6 characters`)
      continue
    }

    const role: Role = VALID_ROLES.includes(roleRaw as Role) ? (roleRaw as Role) : 'LEARNER'

    try {
      const exists = await prisma.user.findUnique({ where: { email }, select: { id: true } })
      if (exists) { results.skipped++; continue }

      const hashed = await bcrypt.hash(password, 10)
      await prisma.user.create({ data: { name, email, password: hashed, role } })
      results.imported++
    } catch {
      results.errors.push(`Row ${lineNum}: failed to create user "${email}"`)
    }
  }

  return NextResponse.json(results)
}

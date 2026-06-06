import { auth } from "@/lib/auth"
import { NextResponse } from "next/server"

// Routes only ADMIN / INSTRUCTOR may access
const ADMIN_ONLY_ROUTES = new Set([
  '/dashboard',
  '/users',
  '/reports',
  '/settings',
  '/academies',
])

// Route prefixes only ADMIN / INSTRUCTOR may access
const ADMIN_ONLY_PREFIXES = [
  '/courses/new',
  '/exams/new',
]

export default auth((req) => {
  const { nextUrl } = req
  const session = req.auth

  // Not authenticated – redirect to /login
  if (!session) {
    return NextResponse.redirect(new URL('/login', nextUrl))
  }

  const isPrivileged =
    session.user.role === 'ADMIN' || session.user.role === 'INSTRUCTOR'
  const path = nextUrl.pathname

  if (!isPrivileged) {
    // Block exact admin-only routes
    if (ADMIN_ONLY_ROUTES.has(path)) {
      return NextResponse.redirect(new URL('/courses', nextUrl))
    }
    // Block admin-only prefixes
    if (
      ADMIN_ONLY_PREFIXES.some(
        (prefix) => path === prefix || path.startsWith(prefix + '/')
      )
    ) {
      return NextResponse.redirect(new URL('/courses', nextUrl))
    }
  }

  return NextResponse.next()
})

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/courses/:path*',
    '/exams/:path*',
    '/learning-paths/:path*',
    '/reports/:path*',
    '/users/:path*',
    '/settings/:path*',
    '/academies/:path*',
    '/certificates/:path*',
    '/learn/:path*',
    '/take/:path*',
  ],
}

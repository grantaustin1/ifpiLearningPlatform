import NextAuth from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import { prisma } from "@/lib/prisma"
import bcrypt from "bcryptjs"

// ─── BUG-001 fix: NEXTAUTH_URL runtime correction ────────────────────────────────
//
// If NEXTAUTH_URL is left pointing at localhost (common on Railway when the
// variable was seeded from a dev .env), override it with the actual production
// URL that Railway itself provides via RAILWAY_PUBLIC_DOMAIN before NextAuth
// initialises.  This runs at module-load time, so it fires before the
// NextAuth() call below captures the environment.
//
// Falls back to deleting NEXTAUTH_URL entirely so that trustHost:true can
// derive the canonical URL from the incoming request Host header.
if (
  typeof process !== "undefined" &&
  process.env.NEXTAUTH_URL?.includes("localhost")
) {
  if (process.env.RAILWAY_PUBLIC_DOMAIN) {
    process.env.NEXTAUTH_URL = `https://${process.env.RAILWAY_PUBLIC_DOMAIN}`
  } else {
    // Non-Railway environment (Vercel, custom host, etc.) — remove stale value
    // and let trustHost pick it up from the request headers.
    delete process.env.NEXTAUTH_URL
  }
}
// ────────────────────────────────────────────────────────────────────

// Extend NextAuth types
declare module "next-auth" {
  interface Session {
    user: {
      id: string
      email: string
      name?: string | null
      role: string
    }
  }
  interface User {
    role?: string
  }
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  // trustHost allows NextAuth to derive the base URL from the incoming request
  // headers, so login/signout redirects work correctly in production without
  // requiring NEXTAUTH_URL to be set to an exact value.
  trustHost: true,
  session: { strategy: "jwt" },
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null

        const user = await prisma.user.findUnique({
          where: { email: credentials.email as string },
        })

        if (!user || !user.password) return null

        const passwordMatch = await bcrypt.compare(
          credentials.password as string,
          user.password
        )

        if (!passwordMatch) return null

        return {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role,
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.role = user.role ?? "LEARNER"
        token.id = user.id
      }
      return token
    },
    async session({ session, token }) {
      if (token && session.user) {
        session.user.id = token.id as string
        session.user.role = token.role as string
      }
      return session
    },
  },
  pages: {
    signIn: "/login",
  },
})

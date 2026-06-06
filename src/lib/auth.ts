import NextAuth from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import { prisma } from "@/lib/prisma"
import bcrypt from "bcryptjs"

// ─── Runtime fix ─────────────────────────────────────────────────────────────
// If NEXTAUTH_URL was left pointing at localhost (e.g. Railway picked it up from
// a dev .env or a mis-configured variable), delete it so that NextAuth v5 falls
// back to trustHost and derives the canonical URL from the incoming request
// headers instead.
if (
  typeof process !== "undefined" &&
  process.env.NEXTAUTH_URL?.includes("localhost")
) {
  delete process.env.NEXTAUTH_URL
}
// ─────────────────────────────────────────────────────────────────────────────

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

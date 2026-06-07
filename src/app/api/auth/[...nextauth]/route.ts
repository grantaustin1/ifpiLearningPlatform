import { handlers } from "@/lib/auth"

// Force dynamic rendering so NextAuth always derives the base URL
// from the live request Host header instead of a build-time-cached
// snapshot. Required for trustHost: true to work correctly in production.
export const dynamic = "force-dynamic"

export const { GET, POST } = handlers

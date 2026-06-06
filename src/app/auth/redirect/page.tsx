import { auth } from "@/lib/auth"
import { redirect } from "next/navigation"

export default async function AuthRedirect() {
  const session = await auth()
  if (!session) redirect("/login")
  if (session.user.role === "ADMIN") redirect("/dashboard")
  redirect("/courses")
}

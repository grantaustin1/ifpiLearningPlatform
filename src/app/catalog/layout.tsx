import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Course Catalog — IFPI Learning",
  description: "Browse our full course catalog",
}

export default function CatalogLayout({ children }: { children: React.ReactNode }) {
  return children
}

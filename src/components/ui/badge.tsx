import * as React from "react"
import { cn } from "@/lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline"
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
        variant === "default" && "border-transparent bg-indigo-600 text-white",
        variant === "secondary" && "border-transparent bg-gray-100 text-gray-900",
        variant === "destructive" && "border-transparent bg-red-500 text-white",
        variant === "outline" && "text-gray-900",
        className
      )}
      {...props}
    />
  )
}

export { Badge }

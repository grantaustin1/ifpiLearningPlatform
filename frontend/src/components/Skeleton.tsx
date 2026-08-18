import { cn } from '@/lib/utils'

interface SkeletonProps {
  className?: string
}

/**
 * Loading skeleton using Tailwind animate-pulse.
 *
 * Usage:
 *   <Skeleton className="h-4 w-[250px]" />
 *   <div className="space-y-2">
 *     <Skeleton className="h-4 w-full" />
 *     <Skeleton className="h-4 w-4/5" />
 *   </div>
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-slate-200', className)}
      aria-hidden="true"
    />
  )
}

import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)) }

export function formatCurrency(cents: number, currency = 'ZAR') {
  return new Intl.NumberFormat('en-ZA', {
    style: 'currency', currency, minimumFractionDigits: 0,
  }).format(cents / 100)
}

export function timeAgo(d: Date | string) {
  const date = typeof d === 'string' ? new Date(d) : d
  const s = Math.floor((Date.now() - date.getTime()) / 1000)
  if (s < 60) return 'just now'
  const m = Math.floor(s / 60); if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

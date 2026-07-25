/**
 * Core domain types for the IFPI Learning Platform frontend.
 * Centralise all DTOs here to eliminate `any` usage across components.
 */

// ── Auth ───────────────────────────────────────────────────────────

export interface User {
  id: number
  email: string
  name?: string | null
  organization_id: number
  roles: string[]
  points: number
  must_change_password?: boolean
  email_verified?: boolean
}

// ── API / HTTP ─────────────────────────────────────────────────────

export interface ApiErrorDetail {
  code?: string
  message?: string
  detail?: string | object
}

/** Standard FastAPI error shape exposed by the backend */
export interface ApiErrorResponse {
  detail?: string | ApiErrorDetail
  error?: ApiErrorDetail
}

/** Generic paginated list wrapper */
export interface Paginated<T> {
  items: T[]
  total: number
  page?: number
  per_page?: number
}

// ── Courses ────────────────────────────────────────────────────────

export interface Course {
  id: number
  title: string
  description?: string | null
  status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED' | string
  organization_id: number
  primary_color?: string | null
  created_at?: string
  updated_at?: string
}

export interface CourseEnrollment {
  course_id: number
  user_id: number
  status: string
  progress_percent?: number
  completed_at?: string | null
}

// ── Comments ───────────────────────────────────────────────────────

export interface Comment {
  id: number
  slide_id: number
  user_id: number
  user_name?: string
  body: string
  created_at: string
}

// ── Certificates ───────────────────────────────────────────────────

export interface Certificate {
  id: number
  user_id: number
  course_id: number
  code: string
  created_at: string
}

// ── Exams ──────────────────────────────────────────────────────────

export interface Exam {
  id: number
  title: string
  course_id: number
  time_limit_minutes?: number
  passing_score?: number
}

export interface ExamQuestion {
  id: number
  exam_id: number
  question_text: string
  question_type: 'multiple_choice' | 'true_false' | 'short_answer' | string
  options?: Record<string, string>
  correct_answer?: string
}

// ── Research / AI ──────────────────────────────────────────────────

export interface ResearchJob {
  id: number
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | string
  input?: { query?: string; depth?: string; course_id?: number | null }
  output?: { source_document_id?: number; chunk_count?: number; source_count?: number }
  error_log?: string | null
  created_at?: string | null
  completed_at?: string | null
}

// ── Payments ───────────────────────────────────────────────────────

export interface CheckoutStatus {
  session_id: string
  status: string
  payment_status: string | null
  amount_cents: number
  currency: string
  course_id: number
  entitled: boolean
  already_processed: boolean
}

// ── Flashcards ─────────────────────────────────────────────────────

export interface FlashcardDeck {
  id: number
  course_id: number
  title: string
  card_count?: number
}

export interface Flashcard {
  id: number
  deck_id: number
  front: string
  back: string
}

// ── Imports ────────────────────────────────────────────────────────

export interface ImportJob {
  id: number
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | string
  file_name?: string
  results?: {
    courses?: Array<{ id: number; title: string }>
    paths?: Array<{ id: number; title: string }>
    errors?: string[]
  }
  created_at?: string
}

// ── Webhooks / API Tokens ──────────────────────────────────────────

export interface ApiToken {
  id: number
  name: string
  token_prefix: string
  created_at: string
  last_used_at?: string | null
}

export interface Webhook {
  id: number
  url: string
  events: string[]
  active: boolean
  created_at: string
}

// ── Organisations ──────────────────────────────────────────────────

export interface Organization {
  id: number
  name: string
  slug?: string
  primary_color?: string | null
  smtp_host?: string | null
  smtp_port?: number | null
  smtp_user?: string | null
  created_at?: string
}

// ── Academy / Cohort ───────────────────────────────────────────────

export interface Academy {
  id: number
  name: string
  description?: string
  organization_id: number
}

// ── Badge / Gamification ───────────────────────────────────────────

export interface BadgeTier {
  id: number
  name: string
  threshold: number
  icon?: string | null
  organization_id: number
}

// ── Audit ──────────────────────────────────────────────────────────

export interface AuditLogEntry {
  id: number
  action: string
  actor_id?: number
  actor_email?: string
  target_type?: string
  target_id?: number
  created_at: string
  metadata?: Record<string, unknown>
}

export interface AuditSummary {
  counts_by_action?: Record<string, number>
}

// ── Subscription / Billing ─────────────────────────────────────────

export interface Subscription {
  id: number
  plan: string
  status: 'active' | 'canceled' | 'past_due' | string
  current_period_end?: string
  amount_cents?: number
  currency?: string
}

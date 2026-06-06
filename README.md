---
type: markdown
---

# IFPI Learning Platform — LMS App

An EasyLMS-inspired Learning Management System built with Next.js 14, Prisma, and SQLite.

---

## 🚀 Quick Start

```bash
cd lms-app

# Install dependencies (already done)
npm install

# Push DB schema & seed demo data
npx prisma db push
npx tsx prisma/seed.ts

# Start development server
npm run dev
# → http://localhost:3000
```

---

## 🔑 Demo Login Credentials

| Role    | Email                | Password    |
|---------|----------------------|-------------|
| Admin   | admin@ifpi.org       | admin123    |
| Learner | learner@ifpi.org     | learner123  |

---

## 📄 Pages & Features

### Public
| Route       | Description |
|-------------|-------------|
| `/`         | Landing page (EasyLMS-style marketing) |
| `/login`    | Email + password sign-in |
| `/register` | Self-registration (creates Admin account) |

### Admin Dashboard (`/dashboard`)
| Route              | Description |
|--------------------|-------------|
| `/dashboard`       | Stats overview, recent activity, quick actions |
| `/courses`         | Course library — list, search, filter |
| `/courses/new`     | **Course builder** — slide-based editor (Text, Video, Audio, Image, PDF) |
| `/exams`           | Exam library |
| `/exams/new`       | **Exam builder** — 6 question types, settings panel |
| `/learning-paths`  | Structured learning journeys (chain courses + exams) |
| `/certificates`    | View all issued certificates |
| `/reports`         | Analytics — completion rates, exam stats, monthly chart |
| `/users`           | User management table |
| `/academies`       | Multi-tenant branded portals |
| `/settings`        | Branding, notifications, certificate defaults |

### Learner Experience
| Route                    | Description |
|--------------------------|-------------|
| `/learn/[courseId]`      | **Course viewer** — slide navigation, progress tracking |
| `/take/[examId]`         | **Exam taker** — timer, question types, instant results |

---

## 🏗️ Tech Stack

| Layer       | Technology |
|-------------|------------|
| Frontend    | Next.js 14 (App Router) + TypeScript |
| Styling     | Tailwind CSS + Radix UI |
| Database    | SQLite (via Prisma ORM) |
| Auth        | NextAuth.js v5 (JWT + credentials) |
| Icons       | Lucide React |
| Charts      | Custom SVG (no external chart lib required) |

---

## 🗄️ Database Schema

Key models: `User`, `Academy`, `Course`, `CourseSlide`, `Exam`, `ExamQuestion`, `ExamAttempt`, `Enrollment`, `Certificate`, `LearningPath`

---

## 🔄 Upgrading to PostgreSQL (production)

Change `.env`:
```
DATABASE_URL="postgresql://user:pass@host:5432/lms_db"
```

Change `prisma/schema.prisma` datasource:
```
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

Re-run `npx prisma db push && npx tsx prisma/seed.ts`

---

## 🎯 EasyLMS Features Replicated

- ✅ Multi-academy (branded portals per organization)
- ✅ Slide-based course builder (Text, Video, Audio, Image, PDF)
- ✅ Exam builder (Multiple choice, True/False, Fill-in-blank, Short answer)
- ✅ Auto-graded exams with pass/fail rates
- ✅ Timer and attempt limits
- ✅ Learning paths (chained courses + exams)
- ✅ Certificate management (with verify codes)
- ✅ Progress tracking per learner
- ✅ Reports & analytics dashboard
- ✅ User management with roles
- ✅ White-label branding settings
- ✅ Flat-fee pricing model (no per-participant fees)

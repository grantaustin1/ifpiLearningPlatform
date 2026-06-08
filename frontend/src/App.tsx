import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from 'contexts/AuthContext'
import LandingPage from 'pages/LandingPage'
import LoginPage from 'pages/auth/LoginPage'
import RegisterPage from 'pages/auth/RegisterPage'
import VerifyCertPage from 'pages/VerifyCertPage'
import AcceptInvitePage from 'pages/AcceptInvitePage'
import DashboardLayout from 'components/layout/DashboardLayout'
import DashboardPage from 'pages/dashboard/DashboardPage'
import CoursesPage from 'pages/dashboard/CoursesPage'
import CourseEditPage from 'pages/dashboard/CourseEditPage'
import ExamsPage from 'pages/dashboard/ExamsPage'
import CertificatesPage from 'pages/dashboard/CertificatesPage'
import UsersPage from 'pages/dashboard/UsersPage'
import ReportsPage from 'pages/dashboard/ReportsPage'
import LeaderboardPage from 'pages/dashboard/LeaderboardPage'
import BillingPage from 'pages/dashboard/BillingPage'
import OutboxPage from 'pages/dashboard/OutboxPage'
import OrganizationSettingsPage from 'pages/dashboard/OrganizationSettingsPage'
import AcademiesPage from 'pages/dashboard/AcademiesPage'
import BadgeTiersPage from 'pages/dashboard/BadgeTiersPage'
import PortalPage from 'pages/PortalPage'
import LearningPathsPage from 'pages/dashboard/LearningPathsPage'
import LearningPathEditPage from 'pages/dashboard/LearningPathEditPage'
import LearnPage from 'pages/learn/LearnPage'
import TakeExamPage from 'pages/take/TakeExamPage'
import CatalogPage from 'pages/catalog/CatalogPage'

function Protected({ children, adminOnly = false }:
{ children: React.ReactNode; adminOnly?: boolean }) {
  const { user, loading } = useAuth()
  if (loading) return <FullPageSpinner />
  if (!user) return <Navigate to="/login" replace />
  if (adminOnly && !['ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR'].some(r => user.roles.includes(r)))
    return <Navigate to="/courses" replace />
  return <>{children}</>
}

function FullPageSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/catalog" element={<CatalogPage />} />
      <Route path="/verify/:code" element={<VerifyCertPage />} />
      <Route path="/accept-invite/:token" element={<AcceptInvitePage />} />
      <Route path="/a/:slug" element={<PortalPage />} />

      <Route element={<Protected><DashboardLayout /></Protected>}>
        <Route path="/dashboard" element={<Protected adminOnly><DashboardPage /></Protected>} />
        <Route path="/courses" element={<CoursesPage />} />
        <Route path="/courses/:id/edit" element={<Protected adminOnly><CourseEditPage /></Protected>} />
        <Route path="/exams" element={<ExamsPage />} />
        <Route path="/learning-paths" element={<LearningPathsPage />} />
        <Route path="/learning-paths/:id/edit" element={<Protected adminOnly><LearningPathEditPage /></Protected>} />
        <Route path="/certificates" element={<CertificatesPage />} />
        <Route path="/users" element={<Protected adminOnly><UsersPage /></Protected>} />
        <Route path="/reports" element={<Protected adminOnly><ReportsPage /></Protected>} />
        <Route path="/leaderboard" element={<LeaderboardPage />} />
        <Route path="/billing" element={<BillingPage />} />
        <Route path="/outbox" element={<Protected adminOnly><OutboxPage /></Protected>} />
        <Route path="/settings" element={<Protected adminOnly><OrganizationSettingsPage /></Protected>} />
        <Route path="/academies" element={<Protected adminOnly><AcademiesPage /></Protected>} />
        <Route path="/badge-tiers" element={<Protected adminOnly><BadgeTiersPage /></Protected>} />
      </Route>

      <Route path="/learn/:courseId" element={<Protected><LearnPage /></Protected>} />
      <Route path="/take/:examId" element={<Protected><TakeExamPage /></Protected>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from 'contexts/AuthContext'
import LandingPage from 'pages/LandingPage'
import LoginPage from 'pages/auth/LoginPage'
import RegisterPage from 'pages/auth/RegisterPage'
import ForgotPasswordPage from 'pages/auth/ForgotPasswordPage'
import ResetPasswordPage from 'pages/auth/ResetPasswordPage'
import ChangePasswordPage from 'pages/auth/ChangePasswordPage'
import VerifyEmailPage from 'pages/auth/VerifyEmailPage'
import VerifyCertPage from 'pages/VerifyCertPage'
import AcceptInvitePage from 'pages/AcceptInvitePage'
import DashboardLayout from 'components/layout/DashboardLayout'
import DashboardPage from 'pages/dashboard/DashboardPage'
import CoursesPage from 'pages/dashboard/CoursesPage'
import CourseEditPage from 'pages/dashboard/CourseEditPage'
import ExamsPage from 'pages/dashboard/ExamsPage'
import CertificatesPage from 'pages/dashboard/CertificatesPage'
import AdminCertificatesPage from 'pages/dashboard/AdminCertificatesPage'
import UsersPage from 'pages/dashboard/UsersPage'
import ReportsPage from 'pages/dashboard/ReportsPage'
import LeaderboardPage from 'pages/dashboard/LeaderboardPage'
import BillingPage from 'pages/dashboard/BillingPage'
import BillingSuccessPage from 'pages/billing/BillingSuccessPage'
import OutboxPage from 'pages/dashboard/OutboxPage'
import OrganizationSettingsPage from 'pages/dashboard/OrganizationSettingsPage'
import AcademiesPage from 'pages/dashboard/AcademiesPage'
import AuditLogPage from 'pages/dashboard/AuditLogPage'
import BadgeTiersPage from 'pages/dashboard/BadgeTiersPage'
import WebhooksPage from 'pages/dashboard/WebhooksPage'
import ImportsPage from 'pages/dashboard/ImportsPage'
import ApiTokensPage from 'pages/dashboard/ApiTokensPage'
import ResearchPage from 'pages/dashboard/ResearchPage'
import FlashcardsAuthoringPage from 'pages/dashboard/FlashcardsAuthoringPage'
import LearnerFlashcardsPage from 'pages/learn/LearnerFlashcardsPage'
import MindMapPage from 'pages/dashboard/MindMapPage'
import PublicCatalogPage from 'pages/PublicCatalogPage'
import PortalPage from 'pages/PortalPage'
import LearningPathsPage from 'pages/dashboard/LearningPathsPage'
import LearningPathEditPage from 'pages/dashboard/LearningPathEditPage'
import LearnPage from 'pages/learn/LearnPage'
import TakeExamPage from 'pages/take/TakeExamPage'
import CatalogPage from 'pages/catalog/CatalogPage'
import CourseDetailPage from 'pages/catalog/CourseDetailPage'
import QueryBuilderPage from 'pages/dashboard/QueryBuilderPage'
import ScheduledReportsPage from 'pages/dashboard/ScheduledReportsPage'
import EmailDiagnosticsPage from 'pages/dashboard/EmailDiagnosticsPage'
import AffiliatePage from 'pages/dashboard/AffiliatePage'
import LiveSessionsPage from 'pages/dashboard/LiveSessionsPage'
import MarketplaceAnalyticsPage from 'pages/dashboard/MarketplaceAnalyticsPage'
import FeedbackAdminPage from 'pages/dashboard/FeedbackAdminPage'
import PreferencesPage from 'pages/dashboard/PreferencesPage'
import Erp360IntegrationsPage from 'pages/dashboard/Erp360IntegrationsPage'
import EntitlementsInspectorPage from 'pages/dashboard/EntitlementsInspectorPage'
import WebhookDeliveriesPage from 'pages/dashboard/WebhookDeliveriesPage'
import { TermsGate } from 'components/TermsGate'
import { KioskShell } from 'components/KioskShell'

function Protected({ children, adminOnly = false }:
{ children: React.ReactNode; adminOnly?: boolean }) {
  const { user, loading } = useAuth()
  if (loading) return <FullPageSpinner />
  if (!user) return <Navigate to="/login" replace />
  // Iter 32 — force password rotation for seeded admin / anyone with
  // the flag set. The /change-password route itself is NOT wrapped
  // in <Protected> so it's still reachable when the flag is on.
  if (user.must_change_password) return <Navigate to="/change-password?forced=1" replace />
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
    <KioskShell>
      <TermsGate />
      <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
      <Route path="/change-password" element={<ChangePasswordPage />} />
      <Route path="/verify-email/:token" element={<VerifyEmailPage />} />
      <Route path="/catalog" element={<CatalogPage />} />
      <Route path="/catalog/:id" element={<CourseDetailPage />} />
      <Route path="/marketplace" element={<CatalogPage />} />
      <Route path="/marketplace/:id" element={<CourseDetailPage />} />
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
        <Route path="/admin/certificates" element={<Protected adminOnly><AdminCertificatesPage /></Protected>} />
        <Route path="/users" element={<Protected adminOnly><UsersPage /></Protected>} />
        <Route path="/reports" element={<Protected adminOnly><ReportsPage /></Protected>} />
        <Route path="/leaderboard" element={<LeaderboardPage />} />
        <Route path="/billing" element={<BillingPage />} />
        <Route path="/outbox" element={<Protected adminOnly><OutboxPage /></Protected>} />
        <Route path="/settings" element={<Protected adminOnly><OrganizationSettingsPage /></Protected>} />
        <Route path="/academies" element={<Protected adminOnly><AcademiesPage /></Protected>} />
        <Route path="/badge-tiers" element={<Protected adminOnly><BadgeTiersPage /></Protected>} />
        <Route path="/audit" element={<Protected adminOnly><AuditLogPage /></Protected>} />
        <Route path="/query-builder" element={<Protected adminOnly><QueryBuilderPage /></Protected>} />
        <Route path="/scheduled-reports" element={<Protected adminOnly><ScheduledReportsPage /></Protected>} />
        <Route path="/email-diagnostics" element={<Protected adminOnly><EmailDiagnosticsPage /></Protected>} />
        <Route path="/affiliate" element={<Protected adminOnly><AffiliatePage /></Protected>} />
        <Route path="/live-sessions" element={<LiveSessionsPage />} />
        <Route path="/marketplace-analytics" element={<Protected adminOnly><MarketplaceAnalyticsPage /></Protected>} />
        <Route path="/feedback-admin" element={<Protected adminOnly><FeedbackAdminPage /></Protected>} />
        <Route path="/preferences" element={<PreferencesPage />} />
        <Route path="/integrations/erp360" element={<Protected adminOnly><Erp360IntegrationsPage /></Protected>} />
        <Route path="/entitlements" element={<Protected adminOnly><EntitlementsInspectorPage /></Protected>} />
        <Route path="/webhooks/deliveries" element={<Protected adminOnly><WebhookDeliveriesPage /></Protected>} />
        <Route path="/webhooks" element={<Protected adminOnly><WebhooksPage /></Protected>} />
        <Route path="/imports" element={<Protected adminOnly><ImportsPage /></Protected>} />
        <Route path="/tokens" element={<Protected adminOnly><ApiTokensPage /></Protected>} />
        <Route path="/research" element={<Protected adminOnly><ResearchPage /></Protected>} />
        <Route path="/courses/:courseId/flashcards" element={<Protected adminOnly><FlashcardsAuthoringPage /></Protected>} />
        <Route path="/courses/:courseId/mindmap" element={<Protected adminOnly><MindMapPage /></Protected>} />
      </Route>

      <Route path="/public" element={<PublicCatalogPage />} />
      <Route path="/verify" element={<PublicCatalogPage />} />
      <Route path="/billing/success" element={<Protected><BillingSuccessPage /></Protected>} />
      <Route path="/learn/:courseId" element={<Protected><LearnPage /></Protected>} />
      <Route path="/learn/:courseId/flashcards" element={<Protected><LearnerFlashcardsPage /></Protected>} />
      <Route path="/take/:examId" element={<Protected><TakeExamPage /></Protected>} />

      <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </KioskShell>
  )
}

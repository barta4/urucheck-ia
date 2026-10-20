import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { CompanyProvider } from './context/CompanyContext'
import { ToastProvider } from './context/ToastContext'
import Layout from './components/Layout'
import SaasLayout from './components/SaasLayout'
import Login from './pages/Login'
import RegisterCompany from './pages/RegisterCompany'
import Dashboard from './pages/Dashboard'

// Route-based code splitting: pages are loaded on demand, shrinking the
// initial bundle (the SaaS admin pages and heavy pages load only when visited).
const Employees = lazy(() => import('./pages/Employees'))
const Logs = lazy(() => import('./pages/Logs'))
const Bonuses = lazy(() => import('./pages/Bonuses'))
const Geofences = lazy(() => import('./pages/Geofences'))
const CompanySettings = lazy(() => import('./pages/CompanySettings'))
const SaasDashboard = lazy(() => import('./pages/SaasDashboard'))
const SaasCompanies = lazy(() => import('./pages/SaasCompanies'))
const SaasBilling = lazy(() => import('./pages/SaasBilling'))
const SaasMercadoPago = lazy(() => import('./pages/SaasMercadoPago'))
const SaasPlans = lazy(() => import('./pages/SaasPlans'))
const SaasAudit = lazy(() => import('./pages/SaasAudit'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
      Cargando...
    </div>
  )
}

function LazyPage({ children }) {
  return <Suspense fallback={<PageLoader />}>{children}</Suspense>
}

function PrivateRoute({ children }) {
  const { user, loading, logout } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen text-gray-400">Cargando...</div>
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'admin' && !user.is_super_admin) {
    logout()
    return <Navigate to="/login" replace />
  }
  return children
}

function SaasRoute({ children }) {
  const { user, loading, logout } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen text-gray-400">Cargando...</div>
  if (!user) return <Navigate to="/login" replace />
  if (!user.is_super_admin) {
    if (user.role === 'admin') {
      return <Navigate to="/dashboard" replace />
    }
    logout()
    return <Navigate to="/login" replace />
  }
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <CompanyProvider>
        <ToastProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<RegisterCompany />} />

              {/* SaaS Super-Admin Routes */}
              <Route path="/saas" element={<SaasRoute><SaasLayout /></SaasRoute>}>
                <Route index element={<Navigate to="/saas/dashboard" replace />} />
                <Route path="dashboard" element={<LazyPage><SaasDashboard /></LazyPage>} />
                <Route path="companies" element={<LazyPage><SaasCompanies /></LazyPage>} />
                <Route path="billing" element={<LazyPage><SaasBilling /></LazyPage>} />
                <Route path="mercadopago" element={<LazyPage><SaasMercadoPago /></LazyPage>} />
                <Route path="plans" element={<LazyPage><SaasPlans /></LazyPage>} />
                <Route path="audit" element={<LazyPage><SaasAudit /></LazyPage>} />
              </Route>

              {/* Company Admin Routes */}
              <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="employees" element={<LazyPage><Employees /></LazyPage>} />
                <Route path="logs" element={<LazyPage><Logs /></LazyPage>} />
                <Route path="bonuses" element={<LazyPage><Bonuses /></LazyPage>} />
                <Route path="geofences" element={<LazyPage><Geofences /></LazyPage>} />
                <Route path="settings" element={<LazyPage><CompanySettings /></LazyPage>} />
                {/* AiChat is rendered as a floating widget inside Layout —
                    a dedicated route would mount it twice on the same screen */}
              </Route>
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </CompanyProvider>
    </AuthProvider>
  )
}

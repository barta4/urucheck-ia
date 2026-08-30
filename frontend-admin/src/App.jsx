import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { CompanyProvider } from './context/CompanyContext'
import { ToastProvider } from './context/ToastContext'
import Layout from './components/Layout'
import SaasLayout from './components/SaasLayout'
import Login from './pages/Login'
import RegisterCompany from './pages/RegisterCompany'
import Dashboard from './pages/Dashboard'
import Employees from './pages/Employees'
import Logs from './pages/Logs'
import Bonuses from './pages/Bonuses'
import Geofences from './pages/Geofences'
import CompanySettings from './pages/CompanySettings'
import AiChat from './pages/AiChat'
import SaasDashboard from './pages/SaasDashboard'
import SaasCompanies from './pages/SaasCompanies'
import SaasBilling from './pages/SaasBilling'
import SaasMercadoPago from './pages/SaasMercadoPago'
import SaasPlans from './pages/SaasPlans'
import SaasAudit from './pages/SaasAudit'

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen text-gray-400">Cargando...</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

function SaasRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen text-gray-400">Cargando...</div>
  if (!user) return <Navigate to="/login" replace />
  if (!user.is_super_admin) return <Navigate to="/dashboard" replace />
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
                <Route path="dashboard" element={<SaasDashboard />} />
                <Route path="companies" element={<SaasCompanies />} />
                <Route path="billing" element={<SaasBilling />} />
                <Route path="mercadopago" element={<SaasMercadoPago />} />
                <Route path="plans" element={<SaasPlans />} />
                <Route path="audit" element={<SaasAudit />} />
              </Route>

              {/* Company Admin Routes */}
              <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="employees" element={<Employees />} />
                <Route path="logs" element={<Logs />} />
                <Route path="bonuses" element={<Bonuses />} />
                <Route path="geofences" element={<Geofences />} />
                <Route path="settings" element={<CompanySettings />} />
                <Route path="ai-chat" element={<AiChat />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </CompanyProvider>
    </AuthProvider>
  )
}

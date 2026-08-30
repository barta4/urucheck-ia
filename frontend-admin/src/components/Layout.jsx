import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useCompany } from '../context/CompanyContext'
import TrialBanner from './TrialBanner'
import AiChat from '../pages/AiChat'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: '📊' },
  { to: '/employees', label: 'Empleados', icon: '👥' },
  { to: '/logs', label: 'Registros', icon: '📋' },
  { to: '/bonuses', label: 'Bonos', icon: '🏆' },
  { to: '/geofences', label: 'Geocercas', icon: '📍' },
  { to: '/settings', label: 'Empresa', icon: '⚙️' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const company = useCompany()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const sidebarBg = company.accent_color || '#1d4ed8'

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-64 flex flex-col" style={{ backgroundColor: sidebarBg }}>
        <div className="p-5 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center flex-shrink-0 overflow-hidden">
              {company.logo_url ? (
                <img src={company.logo_url} alt="Logo" className="w-full h-full object-contain p-1" />
              ) : (
                <span className="text-xl">🏢</span>
              )}
            </div>
            <div className="overflow-hidden">
              <h1 className="text-white font-bold text-sm leading-tight truncate">{company.company_name}</h1>
              <p className="text-white/50 text-xs">Panel Admin</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition ${isActive ? 'bg-white/20 text-white' : 'text-white/60 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              <span>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
          {user?.is_super_admin && (
            <NavLink
              to="/saas"
              className="flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium text-white/60 hover:bg-white/10 hover:text-white border border-white/20 mt-4 bg-white/5"
            >
              <span>🔑</span>
              Panel SaaS Master
            </NavLink>
          )}
        </nav>

        <div className="p-4 border-t border-white/10">
          <p className="text-white/40 text-xs mb-2 truncate">{user?.name}</p>
          <button onClick={handleLogout} className="w-full text-left px-4 py-2 text-sm text-white/60 hover:text-white hover:bg-white/10 rounded-lg transition">
            🚪 Cerrar sesión
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <TrialBanner />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>

      {/* Floating AI Agent Widget */}
      <AiChat />
    </div>
  )
}

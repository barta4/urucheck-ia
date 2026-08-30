import { Outlet, Link, useLocation } from 'react-router-dom'

const NAV = [
  { path: '/saas/dashboard', label: '📊 Dashboard', icon: '' },
  { path: '/saas/companies', label: '🏢 Empresas', icon: '' },
  { path: '/saas/billing', label: '💳 Cobros', icon: '' },
  { path: '/saas/mercadopago', label: '🔗 MercadoPago', icon: '' },
  { path: '/saas/plans', label: '📦 Planes', icon: '' },
  { path: '/saas/audit', label: '📋 Audit Log', icon: '' },
]

export default function SaasLayout() {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 text-white p-6 flex flex-col">
        <div className="mb-8">
          <h1 className="text-xl font-bold">🔑 Super-Admin</h1>
          <p className="text-gray-400 text-xs mt-1">SaaS Management</p>
        </div>

        <nav className="space-y-1 flex-1">
          {NAV.map(item => {
            const active = location.pathname === item.path || location.pathname.startsWith(item.path + '/')
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`block px-4 py-3 rounded-lg text-sm font-medium transition ${
                  active ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-800'
                }`}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div className="pt-4 border-t border-gray-700">
          <Link to="/dashboard" className="block px-4 py-3 rounded-lg text-sm text-gray-400 hover:bg-gray-800 transition">
            ← Volver al Panel Admin
          </Link>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}

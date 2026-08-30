import { useState, useEffect } from 'react'
import { useToast } from '../context/ToastContext'
import api from '../api'

export default function SaasDashboard() {
  const { success, error: showError } = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [apkUrl, setApkUrl] = useState('')
  const [iosUrl, setIosUrl] = useState('')
  const [savingSettings, setSavingSettings] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  useEffect(() => {
    Promise.all([
      api.get('/saas-metrics/dashboard'),
      api.get('/saas-metrics/settings')
    ]).then(([dashRes, settingsRes]) => {
      setData(dashRes.data)
      setApkUrl(settingsRes.data.apk_url || '')
      setIosUrl(settingsRes.data.ios_url || '')
    }).catch(err => {
      console.error('Error loading SaaS data', err)
    }).finally(() => setLoading(false))
  }, [])

  const handleSaveSettings = async (e) => {
    e.preventDefault()
    setSavingSettings(true)
    setSaveSuccess(false)
    try {
      await api.post('/saas-metrics/settings', { apk_url: apkUrl, ios_url: iosUrl })
      setSaveSuccess(true)
      success('Configuración guardada exitosamente')
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch(err) {
      showError(err.response?.data?.detail || 'Error al guardar la configuración')
    } finally {
      setSavingSettings(false)
    }
  }

  if (loading) return <div className="p-6 text-gray-400">Cargando métricas...</div>
  if (!data) return <div className="p-6 text-red-500">Error cargando métricas</div>

  const { companies, revenue, usage, recent_activity } = data

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">📊 Dashboard SaaS</h2>

      {/* App Download Links Config */}
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2 text-base">
          📱 Enlaces de Descarga de la App Móvil (APK / iOS)
        </h3>
        <p className="text-xs text-gray-500 mb-4">
          Defina las URLs donde están alojadas las aplicaciones de Android (APK) e iOS para que los administradores de cada empresa puedan descargarlas directamente desde su panel.
        </p>

        <form onSubmit={handleSaveSettings} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                URL de descarga Android (APK)
              </label>
              <input
                value={apkUrl}
                onChange={e => setApkUrl(e.target.value)}
                placeholder="https://tu-servidor.com/app-release.apk"
                className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                URL de descarga iOS (App Store / IPA)
              </label>
              <input
                value={iosUrl}
                onChange={e => setIosUrl(e.target.value)}
                placeholder="https://apps.apple.com/app/urucheck-ia/id..."
                className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={savingSettings}
              className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {savingSettings ? '⏳ Guardando...' : '💾 Guardar Enlaces'}
            </button>
            {saveSuccess && (
              <p className="text-green-600 text-xs font-medium">✅ Enlaces globales actualizados con éxito</p>
            )}
          </div>
        </form>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="Total Empresas" value={companies.total} icon="🏢" color="blue" />
        <KpiCard label="Activas" value={companies.active} icon="✅" color="green" />
        <KpiCard label="En Trial" value={companies.trial} icon="🧪" color="yellow" />
        <KpiCard label="MRR (USD)" value={`$${revenue.mrr.toLocaleString()} USD`} icon="💰" color="purple" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="ARR (USD)" value={`$${revenue.arr.toLocaleString()} USD`} icon="📈" color="indigo" />
        <KpiCard label="Churn Rate" value={`${revenue.churn_rate}%`} icon="📉" color="red" />
        <KpiCard label="Empleados Totales" value={usage.total_employees} icon="👥" color="teal" />
        <KpiCard label="Ingresos Totales" value={`$${revenue.total_revenue.toLocaleString()} USD`} icon="💵" color="emerald" />
      </div>

      {/* Alerts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-amber-800 font-medium">⚠️ Trials por expirar (3 días)</p>
          <p className="text-3xl font-bold text-amber-600 mt-1">{usage.expiring_trials}</p>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <p className="text-blue-800 font-medium">🆕 Nuevas empresas (7 días)</p>
          <p className="text-3xl font-bold text-blue-600 mt-1">{usage.recent_signups}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Plans Distribution */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="font-semibold text-gray-900 mb-4">📦 Distribución por Plan</h3>
          {Object.entries(usage.plans_distribution).map(([plan, count]) => (
            <div key={plan} className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm font-medium text-gray-700">{plan}</span>
              <span className="text-sm font-bold text-gray-900">{count}</span>
            </div>
          ))}
        </div>

        {/* Top Companies */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="font-semibold text-gray-900 mb-4">🏆 Más Activas (este mes)</h3>
          {usage.top_companies.map((c, i) => (
            <div key={c.slug} className="flex items-center justify-between py-2 border-b border-gray-100">
              <div>
                <span className="text-sm font-medium text-gray-700">#{i + 1} {c.name}</span>
                <p className="text-xs text-gray-400">{c.slug}</p>
              </div>
              <span className="text-sm font-bold text-blue-600">{c.log_count} registros</span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h3 className="font-semibold text-gray-900 mb-4">📋 Actividad Reciente</h3>
        <div className="space-y-2">
          {recent_activity.slice(0, 15).map(log => (
            <div key={log.id} className="flex items-center gap-3 py-2 border-b border-gray-50 text-sm">
              <span className="text-gray-400 w-32 truncate">{new Date(log.created_at).toLocaleString('es')}</span>
              <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded text-xs font-medium">{log.action}</span>
              <span className="text-gray-700 font-medium">{log.company_name}</span>
              {log.user_name && <span className="text-gray-400">por {log.user_name}</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function KpiCard({ label, value, icon, color }) {
  const colors = {
    blue: 'bg-blue-50 border-blue-200',
    green: 'bg-green-50 border-green-200',
    yellow: 'bg-yellow-50 border-yellow-200',
    purple: 'bg-purple-50 border-purple-200',
    red: 'bg-red-50 border-red-200',
    indigo: 'bg-indigo-50 border-indigo-200',
    teal: 'bg-teal-50 border-teal-200',
    emerald: 'bg-emerald-50 border-emerald-200',
  }

  return (
    <div className={`${colors[color]} border rounded-xl p-4`}>
      <p className="text-sm text-gray-600">{icon} {label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
    </div>
  )
}

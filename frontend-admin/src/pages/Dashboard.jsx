import { useState, useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import { useCompany } from '../context/CompanyContext'
import api from '../api'

const STATUS_CONFIG = {
  on_time: { label: 'En hora', class: 'bg-green-100 text-green-700', dot: 'bg-green-500' },
  late: { label: 'Tarde', class: 'bg-red-100 text-red-700', dot: 'bg-red-500' },
  absent: { label: 'Ausente', class: 'bg-gray-100 text-gray-600', dot: 'bg-gray-400' },
  pending: { label: 'Pendiente', class: 'bg-yellow-100 text-yellow-700', dot: 'bg-yellow-400' },
}

function StatCard({ label, value, color }) {
  return (
    <div className={`bg-white rounded-xl p-6 shadow-sm border-l-4 ${color}`}>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const company = useCompany()

  const fetchData = async () => {
    try {
      const res = await api.get('/dashboard/today')
      setData(res.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // refresh every 30s
    return () => clearInterval(interval)
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <div className="text-gray-500">Cargando...</div>
    </div>
  )

  const summary = data?.summary || {}
  const employees = Array.isArray(data?.employees) ? data.employees : []
  const mapEmployees = employees.filter(e => e.latitude && e.longitude)

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
          <p className="text-gray-500 text-sm">{new Date().toLocaleDateString('es', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
        </div>
        <button onClick={fetchData} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition">
          🔄 Actualizar
        </button>
      </div>

      {/* Mobile App Download Banner */}
      {(company.apk_url || company.ios_url) && (
        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-2xl p-6 text-white shadow-md flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="space-y-2">
            <h4 className="text-lg font-bold flex items-center gap-2">
              📱 Descarga la App Móvil para Empleados
            </h4>
            <p className="text-sm text-blue-100 max-w-xl">
              Permite que tus empleados marquen asistencia, consulten sus horarios, verifiquen sus rachas y registren su rostro directamente desde sus dispositivos móviles.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
            {company.apk_url && (
              <a
                href={company.apk_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 md:flex-none text-center bg-white text-blue-700 hover:bg-blue-50 px-5 py-2.5 rounded-xl text-sm font-semibold transition shadow whitespace-nowrap"
              >
                🤖 Descargar APK (Android)
              </a>
            )}
            {company.ios_url && (
              <a
                href={company.ios_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 md:flex-none text-center bg-gray-900 text-white hover:bg-gray-800 px-5 py-2.5 rounded-xl text-sm font-semibold transition border border-gray-700 shadow whitespace-nowrap"
              >
                🍏 Descargar para iOS
              </a>
            )}
          </div>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total programados" value={summary.total || 0} color="border-blue-500" />
        <StatCard label="En hora" value={summary.on_time || 0} color="border-green-500" />
        <StatCard label="Tarde" value={summary.late || 0} color="border-red-500" />
        <StatCard label="Ausentes" value={summary.absent || 0} color="border-gray-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Employee table */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h3 className="font-semibold text-gray-900">Estado de empleados</h3>
          </div>
          <div className="overflow-auto max-h-96">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="px-4 py-3 text-left">Nombre</th>
                  <th className="px-4 py-3 text-left">Entrada</th>
                  <th className="px-4 py-3 text-left">Estado</th>
                  <th className="px-4 py-3 text-left">Racha</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {employees.map(emp => {
                  const cfg = STATUS_CONFIG[emp.status] || STATUS_CONFIG.pending
                  return (
                    <tr key={emp.employee_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium">{emp.name}</td>
                      <td className="px-4 py-3 text-gray-500">
                        {emp.check_in_time ? new Date(emp.check_in_time).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }) : '-'}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.class}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`}></span>
                          {cfg.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {emp.streak > 0 ? `🔥 ${emp.streak}d` : '-'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Map */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h3 className="font-semibold text-gray-900">Mapa de marcaciones</h3>
          </div>
          <div className="h-80">
            {mapEmployees.length > 0 ? (
              <MapContainer
                center={[mapEmployees[0].latitude, mapEmployees[0].longitude]}
                zoom={13}
                style={{ height: '100%', width: '100%' }}
              >
                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                {mapEmployees.map(emp => (
                  <Marker key={emp.employee_id} position={[emp.latitude, emp.longitude]}>
                    <Popup>
                      <strong>{emp.name}</strong><br/>
                      {STATUS_CONFIG[emp.status]?.label}<br/>
                      {emp.check_in_time ? new Date(emp.check_in_time).toLocaleTimeString() : ''}
                    </Popup>
                  </Marker>
                ))}
              </MapContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400">
                Sin ubicaciones registradas hoy
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

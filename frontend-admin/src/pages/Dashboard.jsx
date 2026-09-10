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
  const [requestingMap, setRequestingMap] = useState({})
  const [requestingAll, setRequestingAll] = useState(false)
  const [actionMsg, setActionMsg] = useState(null)
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

  const handleRequestLocation = async (employeeId, employeeName) => {
    setRequestingMap(prev => ({ ...prev, [employeeId]: true }))
    try {
      const res = await api.post(`/locations/request/${employeeId}`)
      setActionMsg({
        type: 'success',
        text: `Solicitud despachada a ${employeeName}. La app reportará su ubicación.`
      })
      setTimeout(() => setActionMsg(null), 5000)
      setTimeout(fetchData, 3500)
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al solicitar ubicación'
      setActionMsg({ type: 'error', text: msg })
      setTimeout(() => setActionMsg(null), 5000)
    } finally {
      setRequestingMap(prev => ({ ...prev, [employeeId]: false }))
    }
  }

  const handleRequestAll = async () => {
    setRequestingAll(true)
    try {
      const res = await api.post('/locations/request-all')
      setActionMsg({
        type: 'success',
        text: res.data?.message || 'Solicitud enviada a los empleados activos.'
      })
      setTimeout(() => setActionMsg(null), 5000)
      setTimeout(fetchData, 4000)
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al solicitar ubicaciones'
      setActionMsg({ type: 'error', text: msg })
      setTimeout(() => setActionMsg(null), 5000)
    } finally {
      setRequestingAll(false)
    }
  }

  const formatLocationTime = (isoString) => {
    if (!isoString) return null
    try {
      const date = new Date(isoString)
      const now = new Date()
      const diffSecs = Math.floor((now - date) / 1000)
      if (diffSecs < 60) return 'Hace unos segundos'
      const diffMins = Math.floor(diffSecs / 60)
      if (diffMins < 60) return `Hace ${diffMins} min`
      const diffHours = Math.floor(diffMins / 60)
      return `Hace ${diffHours}h`
    } catch {
      return null
    }
  }

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
      {/* Alert toast banner */}
      {actionMsg && (
        <div className={`p-4 rounded-xl flex items-center justify-between shadow-sm transition ${
          actionMsg.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          <div className="flex items-center gap-2 text-sm font-medium">
            <span>{actionMsg.type === 'success' ? '✅' : '⚠️'}</span>
            <span>{actionMsg.text}</span>
          </div>
          <button onClick={() => setActionMsg(null)} className="text-xs text-gray-500 hover:text-gray-700 font-bold ml-4">✕</button>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
          <p className="text-gray-500 text-sm">{new Date().toLocaleDateString('es', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRequestAll}
            disabled={requestingAll}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition shadow-sm disabled:opacity-50 flex items-center gap-1.5"
            title="Solicitar ubicación en vivo a todos los empleados con app activa"
          >
            {requestingAll ? '⏳ Solicitando...' : '📍 Solicitar a Todos'}
          </button>
          <button onClick={fetchData} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition shadow-sm">
            🔄 Actualizar
          </button>
        </div>
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
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Estado y Ubicación de Empleados</h3>
            <span className="text-xs text-gray-400">Total: {employees.length}</span>
          </div>
          <div className="overflow-auto max-h-96">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="px-4 py-3 text-left">Nombre</th>
                  <th className="px-4 py-3 text-left">Estado</th>
                  <th className="px-4 py-3 text-left">Último Punto GPS</th>
                  <th className="px-4 py-3 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {employees.map(emp => {
                  const cfg = STATUS_CONFIG[emp.status] || STATUS_CONFIG.pending
                  const isLive = emp.location_source === 'on_demand' || emp.location_source === 'shift_tracking'
                  const locTime = formatLocationTime(emp.location_updated_at)

                  return (
                    <tr key={emp.employee_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900">{emp.name}</div>
                        <div className="text-xs text-gray-400">
                          {emp.check_in_time ? `Entrada: ${new Date(emp.check_in_time).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })}` : 'Sin entrada'}
                          {emp.streak > 0 && ` • 🔥 ${emp.streak}d`}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.class}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`}></span>
                          {cfg.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {emp.latitude && emp.longitude ? (
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-1.5">
                              <span className={`inline-block w-2 h-2 rounded-full ${isLive ? 'bg-emerald-500 animate-pulse' : 'bg-gray-400'}`}></span>
                              <span className="text-xs font-medium text-gray-700">
                                {locTime || 'Hoy'}
                              </span>
                            </div>
                            <div className="text-[11px] text-gray-400">
                              {emp.location_source === 'on_demand' ? '📍 Bajo demanda' : emp.location_source === 'shift_tracking' ? '📡 En turno' : '🕒 En entrada'}
                              {emp.location_accuracy ? ` (±${Math.round(emp.location_accuracy)}m)` : ''}
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">Sin señal GPS</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleRequestLocation(emp.employee_id, emp.name)}
                          disabled={!emp.has_device || requestingMap[emp.employee_id]}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-40 disabled:hover:bg-blue-50 transition"
                          title={emp.has_device ? 'Solicitar al móvil que reporte su posición actual' : 'El empleado no tiene la app móvil vinculada'}
                        >
                          {requestingMap[emp.employee_id] ? '⏳ Pidiendo...' : '📍 Solicitar'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Map */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Mapa de Ubicaciones (Último Punto)</h3>
            <span className="text-xs text-emerald-600 font-medium flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              {mapEmployees.length} localizado(s)
            </span>
          </div>
          <div className="h-96 flex-1">
            {mapEmployees.length > 0 ? (
              <MapContainer
                center={[mapEmployees[0].latitude, mapEmployees[0].longitude]}
                zoom={13}
                style={{ height: '100%', width: '100%' }}
              >
                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                {mapEmployees.map(emp => {
                  const isLive = emp.location_source === 'on_demand' || emp.location_source === 'shift_tracking'
                  const locTime = formatLocationTime(emp.location_updated_at)

                  return (
                    <Marker key={emp.employee_id} position={[emp.latitude, emp.longitude]}>
                      <Popup>
                        <div className="p-1 space-y-1 text-xs">
                          <strong className="text-sm text-gray-900">{emp.name}</strong>
                          <div>
                            <span className="text-gray-500">Estado: </span>
                            <span className="font-medium">{STATUS_CONFIG[emp.status]?.label || 'Pendiente'}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Última señal: </span>
                            <span className="font-semibold text-blue-700">{locTime || 'Hoy'}</span>
                          </div>
                          <div className="text-gray-400 text-[10px]">
                            {emp.location_source === 'on_demand' ? '📍 Solicitud en vivo' : emp.location_source === 'shift_tracking' ? '📡 Turno de trabajo' : '🕒 Marcación de entrada'}
                            {emp.location_accuracy ? ` • Precisión: ±${Math.round(emp.location_accuracy)}m` : ''}
                          </div>
                          <button
                            onClick={() => handleRequestLocation(emp.employee_id, emp.name)}
                            disabled={!emp.has_device || requestingMap[emp.employee_id]}
                            className="mt-2 w-full px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-semibold disabled:opacity-50 transition"
                          >
                            {requestingMap[emp.employee_id] ? '⏳ Solicitando...' : '🔄 Solicitar en vivo'}
                          </button>
                        </div>
                      </Popup>
                    </Marker>
                  )
                })}
              </MapContainer>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 p-6 text-center space-y-2">
                <span className="text-3xl">🗺️</span>
                <p className="font-medium">Sin ubicaciones registradas hoy</p>
                <p className="text-xs max-w-xs text-gray-400">
                  Usa el botón "📍 Solicitar" en la tabla para pedir las coordenadas a un empleado en cualquier momento.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

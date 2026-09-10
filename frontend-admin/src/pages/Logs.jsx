import { useState, useEffect } from 'react'
import { useToast } from '../context/ToastContext'
import api from '../api'
import { STATUS_LABELS, TYPE_LABELS } from '../constants/attendance'
import { downloadBlob } from '../utils/fileDownloader'

const getDefaultDateRange = () => {
  const today = new Date()
  const thirtyDaysAgo = new Date()
  thirtyDaysAgo.setDate(today.getDate() - 30)

  const format = (d) => {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }

  return {
    date_from: format(thirtyDaysAgo),
    date_to: format(today)
  }
}

export default function Logs() {
  const { success, error: showError, info } = useToast()
  const defaultDates = getDefaultDateRange()
  const [logs, setLogs] = useState([])
  const [employees, setEmployees] = useState([])
  const [filters, setFilters] = useState({
    employee_id: '',
    date_from: defaultDates.date_from,
    date_to: defaultDates.date_to,
    status: ''
  })
  const [loading, setLoading] = useState(false)
  const [downloadingExcel, setDownloadingExcel] = useState(false)
  const [photoModal, setPhotoModal] = useState(null)
  const token = localStorage.getItem('token') || ''

  useEffect(() => {
    api.get('/employees/').then(r => setEmployees(r.data))
    fetchLogs()
  }, [])

  const fetchLogs = async (customFilters = null) => {
    setLoading(true)
    try {
      const active = customFilters || filters
      const def = getDefaultDateRange()
      const dFrom = active.date_from || def.date_from
      const dTo = active.date_to || def.date_to

      const params = {}
      if (active.employee_id) params.employee_id = active.employee_id
      if (dFrom) params.date_from = dFrom
      if (dTo) params.date_to = dTo
      if (active.status) params.status = active.status
      const res = await api.get('/dashboard/logs', { params })
      setLogs(res.data)
    } catch (err) {
      console.error('Error al cargar registros', err)
      showError('Error al cargar registros de asistencia')
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadExcel = async () => {
    setDownloadingExcel(true)
    try {
      const def = getDefaultDateRange()
      const dFrom = filters.date_from || def.date_from
      const dTo = filters.date_to || def.date_to

      // Asegurar que el estado visual del input refleje el rango seleccionado
      if (!filters.date_from || !filters.date_to) {
        setFilters(f => ({ ...f, date_from: dFrom, date_to: dTo }))
      }

      const params = {}
      if (filters.employee_id) params.employee_id = filters.employee_id
      if (dFrom) params.date_from = dFrom
      if (dTo) params.date_to = dTo
      if (filters.status) params.status = filters.status

      const res = await api.get('/dashboard/logs/export', { params, responseType: 'blob' })
      const disposition = res.headers['content-disposition']
      let filename = `Registros_Asistencia_${dFrom}_al_${dTo}.xlsx`
      if (disposition && disposition.includes('filename=')) {
        filename = disposition.split('filename=')[1].replace(/["']/g, '')
      }

      downloadBlob(res.data, filename, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
      success('Registros exportados en Excel correctamente')
    } catch (error) {
      console.error("Error descargando archivo", error)
      let msg = "Error al descargar el archivo Excel."
      if (error.response?.data instanceof Blob) {
        try {
          const text = await error.response.data.text()
          const json = JSON.parse(text)
          if (json.detail) msg = json.detail
        } catch (_) {}
      } else if (error.response?.data?.detail) {
        msg = error.response.data.detail
      }
      showError(msg)
    } finally {
      setDownloadingExcel(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Registros de asistencia</h2>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap gap-3 items-center">
        <select
          value={filters.employee_id}
          onChange={e => setFilters({ ...filters, employee_id: e.target.value })}
          className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Todos los empleados</option>
          {employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>

        <div className="flex items-center gap-1.5">
          <input
            type="date"
            value={filters.date_from}
            onChange={e => setFilters({ ...filters, date_from: e.target.value })}
            className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            title="Fecha desde"
          />
          <span className="text-gray-400 text-xs">hasta</span>
          <input
            type="date"
            value={filters.date_to}
            onChange={e => setFilters({ ...filters, date_to: e.target.value })}
            className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            title="Fecha hasta"
          />
        </div>

        <button
          type="button"
          onClick={() => {
            const def = getDefaultDateRange()
            const updated = { ...filters, date_from: def.date_from, date_to: def.date_to }
            setFilters(updated)
            fetchLogs(updated)
          }}
          className="px-2.5 py-2 text-xs text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg font-medium transition"
          title="Seleccionar los últimos 30 días automáticamente"
        >
          📅 Último mes
        </button>

        <select
          value={filters.status}
          onChange={e => setFilters({ ...filters, status: e.target.value })}
          className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Todos los estados</option>
          <option value="on_time">En hora</option>
          <option value="late">Tarde</option>
          <option value="warning">Advertencia</option>
        </select>

        <button
          onClick={() => fetchLogs()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition"
        >
          Filtrar
        </button>
        <button
          onClick={handleDownloadExcel}
          disabled={downloadingExcel}
          className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition flex items-center gap-2 ml-auto shadow-sm"
        >
          <span>📊</span> {downloadingExcel ? 'Descargando...' : 'Descargar Excel'}
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b text-sm text-gray-500">
          {logs.length} registros encontrados
        </div>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-3 text-left">Foto</th>
                <th className="px-4 py-3 text-left">Empleado</th>
                <th className="px-4 py-3 text-left">Turno / Ubicación</th>
                <th className="px-4 py-3 text-left">Tipo</th>
                <th className="px-4 py-3 text-left">Hora</th>
                <th className="px-4 py-3 text-left">Estado</th>
                <th className="px-4 py-3 text-left">GPS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr><td colSpan={7} className="px-6 py-8 text-center text-gray-400">Cargando...</td></tr>
              ) : logs.map(log => {
                const statusCfg = STATUS_LABELS[log.status]
                const photoFilename = log.photo_path ? log.photo_path.split('/').pop() : null
                return (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      {photoFilename ? (
                        <button onClick={() => setPhotoModal(`/api/photos/${photoFilename}?token=${token}`)}>
                          <img
                            src={`/api/photos/${photoFilename}?token=${token}`}
                            alt="selfie"
                            className="w-10 h-10 rounded-full object-cover border-2 border-gray-200 hover:border-blue-400 transition"
                          />
                        </button>
                      ) : (
                        <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center text-gray-400 text-xs">—</div>
                      )}
                    </td>
                    <td className="px-4 py-3 font-medium">{log.employee_name}</td>
                    <td className="px-4 py-3">
                      <p className="text-xs font-semibold text-gray-800">{log.slot_name || 'Turno Regular'}</p>
                      {log.geofence_name && (
                        <span className="text-[10px] text-emerald-700 font-medium">📍 {log.geofence_name}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      <span>{TYPE_LABELS[log.type] || log.type}</span>
                      {log.early_minutes > 0 && (
                        <span className="ml-1.5 px-1.5 py-0.5 bg-amber-100 text-amber-800 text-[10px] font-bold rounded">
                          -{log.early_minutes}m antes
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(log.timestamp).toLocaleString('es', {
                        day: '2-digit', month: '2-digit', year: 'numeric',
                        hour: '2-digit', minute: '2-digit'
                      })}
                    </td>
                    <td className="px-4 py-3">
                      {statusCfg ? (
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusCfg.class}`}>
                          {statusCfg.label}
                        </span>
                      ) : '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {log.latitude ? `${Number(log.latitude).toFixed(4)}, ${Number(log.longitude).toFixed(4)}` : '-'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Photo modal */}
      {photoModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50" onClick={() => setPhotoModal(null)}>
          <img src={photoModal} alt="Validación" className="max-w-sm max-h-[80vh] rounded-2xl shadow-2xl object-contain" />
        </div>
      )}
    </div>
  )
}

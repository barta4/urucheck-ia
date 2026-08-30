import { useState, useEffect } from 'react'
import api from '../api'

export default function SaasAudit() {
  const [logs, setLogs] = useState([])
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState({ action: '', date_from: '', date_to: '', limit: 50 })

  useEffect(() => {
    load()
    api.get('/audit/actions').then(r => setActions(r.data)).catch(() => {})
  }, [filters])

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/audit/logs', { params: { ...filters, offset: 0 } })
      setLogs(res.data.logs)
      setTotal(res.data.total)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">📋 Audit Log ({total} registros)</h2>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Acción</label>
          <select value={filters.action} onChange={e => setFilters({...filters, action: e.target.value})} className="border rounded-lg px-3 py-2 text-sm">
            <option value="">Todas</option>
            {actions.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Desde</label>
          <input type="date" value={filters.date_from} onChange={e => setFilters({...filters, date_from: e.target.value})} className="border rounded-lg px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Hasta</label>
          <input type="date" value={filters.date_to} onChange={e => setFilters({...filters, date_to: e.target.value})} className="border rounded-lg px-3 py-2 text-sm" />
        </div>
        <button onClick={load} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">Filtrar</button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-4 py-3 text-left">Fecha</th>
              <th className="px-4 py-3 text-left">Acción</th>
              <th className="px-4 py-3 text-left">Empresa</th>
              <th className="px-4 py-3 text-left">Usuario</th>
              <th className="px-4 py-3 text-left">Recurso</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan="5" className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan="5" className="px-4 py-8 text-center text-gray-400">Sin registros</td></tr>
            ) : logs.map(log => (
              <tr key={log.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-500 text-xs">{new Date(log.created_at).toLocaleString('es')}</td>
                <td className="px-4 py-3">
                  <span className="px-2 py-1 rounded text-xs font-medium bg-blue-50 text-blue-700">{log.action}</span>
                </td>
                <td className="px-4 py-3 font-medium">{log.company_name}</td>
                <td className="px-4 py-3 text-gray-500">{log.user_name || 'Sistema'}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {log.resource} {log.resource_id && `(${log.resource_id.slice(0, 8)}...)`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

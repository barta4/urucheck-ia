import { useState, useEffect } from 'react'
import { useToast } from '../context/ToastContext'
import api from '../api'

const STATUS_COLORS = {
  trial: 'bg-yellow-100 text-yellow-700',
  active: 'bg-green-100 text-green-700',
  grace: 'bg-orange-100 text-orange-700',
  suspended: 'bg-red-100 text-red-700',
  cancelled: 'bg-gray-100 text-gray-500',
}

export default function SaasCompanies() {
  const { success, error: showError, warning } = useToast()
  const [companies, setCompanies] = useState([])
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [planFilter, setPlanFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [changePlanFor, setChangePlanFor] = useState(null)
  const [selectedPlan, setSelectedPlan] = useState('')
  const [companyToDelete, setCompanyToDelete] = useState(null)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    load()
    api.get('/plans/').then(r => setPlans(r.data)).catch(() => {})
  }, [])

  const load = async () => {
    try {
      const res = await api.get('/saas-metrics/companies')
      setCompanies(res.data)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  const handleStatusChange = async (action, company) => {
    setActionLoading(`${company.id}-${action}`)
    try {
      const statusMap = { 'Suspender': 'suspended', 'Reactivar': 'active', 'Cancelar': 'cancelled' }
      await api.patch(`/companies/${company.id}`, { status: statusMap[action] })
      success(`Estado de ${company.name} actualizado a ${statusMap[action]}`)
      load()
    } catch (err) { showError(err.response?.data?.detail || 'Error al cambiar estado') }
    finally { setActionLoading(null) }
  }

  const handlePlanChange = async (company) => {
    if (!selectedPlan) return warning('Selecciona un plan antes de continuar')
    setActionLoading(`${company.id}-plan`)
    try {
      await api.post(`/companies/${company.id}/assign-plan`, null, { params: { plan_id: selectedPlan } })
      success(`Plan asignado a ${company.name} con éxito`)
      setChangePlanFor(null)
      setSelectedPlan('')
      load()
    } catch (err) { showError(err.response?.data?.detail || 'Error al cambiar plan') }
    finally { setActionLoading(null) }
  }

  const handleDeleteCompany = async () => {
    if (!companyToDelete) return
    if (deleteConfirmText.trim().toUpperCase() !== 'ELIMINAR') {
      return warning('Escribe "ELIMINAR" en mayúsculas para confirmar la acción')
    }
    setActionLoading(`delete-${companyToDelete.id}`)
    try {
      await api.delete(`/companies/${companyToDelete.id}?force=true`)
      success(`Empresa "${companyToDelete.name}" eliminada exitosamente`)
      setCompanyToDelete(null)
      setDeleteConfirmText('')
      load()
    } catch (err) {
      showError(err.response?.data?.detail || 'Error al eliminar empresa')
    } finally {
      setActionLoading(null)
    }
  }

  const filtered = companies.filter(c => {
    if (filter && !c.name.toLowerCase().includes(filter.toLowerCase()) && !c.slug.includes(filter.toLowerCase())) return false
    if (planFilter && c.plan_name !== planFilter) return false
    if (statusFilter && c.status !== statusFilter) return false
    return true
  })

  if (loading) return <div className="p-6 text-gray-400">Cargando empresas...</div>

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">🏢 Gestión de Empresas ({companies.length})</h2>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Buscar</label>
          <input placeholder="Nombre o slug..." value={filter} onChange={e => setFilter(e.target.value)} className="border rounded-lg px-3 py-2 text-sm w-56" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Plan</label>
          <select value={planFilter} onChange={e => setPlanFilter(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
            <option value="">Todos</option>
            {plans.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Estado</label>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
            <option value="">Todos</option>
            {Object.keys(STATUS_COLORS).map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        {(filter || planFilter || statusFilter) && (
          <button onClick={() => { setFilter(''); setPlanFilter(''); setStatusFilter('') }} className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700">
            ✕ Limpiar filtros
          </button>
        )}
      </div>

      {/* Companies table */}
      <div className="bg-white rounded-xl shadow-sm overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-4 py-3 text-left">Empresa</th>
              <th className="px-4 py-3 text-left">Plan</th>
              <th className="px-4 py-3 text-left">Estado</th>
              <th className="px-4 py-3 text-left">Empleados</th>
              <th className="px-4 py-3 text-left">Actividad</th>
              <th className="px-4 py-3 text-left">Precio</th>
              <th className="px-4 py-3 text-left">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.map(c => (
              <tr key={c.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-gray-900">{c.name}</p>
                  <p className="text-xs text-gray-400 font-mono">{c.slug}</p>
                  <p className="text-xs text-gray-400">{c.admin_email}</p>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1">
                    <span className="px-2 py-1 rounded text-xs font-medium bg-blue-50 text-blue-700">
                      {c.plan_name || 'Free'}
                    </span>
                    <button onClick={() => { setChangePlanFor(c); setSelectedPlan(c.plan_id || '') }} className="text-xs text-blue-500 hover:text-blue-700" title="Cambiar plan">
                      ✏️
                    </button>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_COLORS[c.status] || 'bg-gray-100 text-gray-500'}`}>
                    {c.status}
                  </span>
                  {c.trial_ends_at && c.status === 'trial' && (
                    <p className="text-xs text-yellow-600 mt-1">
                      Trial hasta {new Date(c.trial_ends_at).toLocaleDateString('es')}
                    </p>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="font-medium text-gray-900">{c.active_employees}</span>
                </td>
                <td className="px-4 py-3">
                  <p className="text-xs text-gray-500">{c.today_logs} hoy</p>
                  {c.last_activity && (
                    <p className="text-xs text-gray-400">Última: {new Date(c.last_activity).toLocaleDateString('es')}</p>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="font-medium text-gray-900">${c.plan_price || 0}</span>
                  <span className="text-xs text-gray-400"> USD/mes</span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {c.status === 'trial' && (
                      <button onClick={() => handleStatusChange('Suspender', c)} disabled={actionLoading === `${c.id}-Suspender`} className="px-2.5 py-1 bg-orange-50 text-orange-600 font-medium rounded-lg text-xs hover:bg-orange-100 disabled:opacity-50 transition">
                        Suspender
                      </button>
                    )}
                    {(c.status === 'suspended' || c.status === 'grace') && (
                      <button onClick={() => handleStatusChange('Reactivar', c)} disabled={actionLoading === `${c.id}-Reactivar`} className="px-2.5 py-1 bg-green-50 text-green-600 font-medium rounded-lg text-xs hover:bg-green-100 disabled:opacity-50 transition">
                        Reactivar
                      </button>
                    )}
                    {c.status !== 'cancelled' && (
                      <button onClick={() => handleStatusChange('Cancelar', c)} disabled={actionLoading === `${c.id}-Cancelar`} className="px-2.5 py-1 bg-gray-100 text-gray-700 font-medium rounded-lg text-xs hover:bg-gray-200 disabled:opacity-50 transition">
                        Cancelar
                      </button>
                    )}
                    <button
                      onClick={() => {
                        setCompanyToDelete(c)
                        setDeleteConfirmText('')
                      }}
                      className="px-2.5 py-1 bg-red-50 text-red-600 font-medium rounded-lg text-xs hover:bg-red-100 transition inline-flex items-center gap-1"
                      title="Eliminar empresa"
                    >
                      🗑️ Eliminar
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Change Plan Modal */}
      {changePlanFor && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h3 className="font-semibold text-lg">Cambiar plan — {changePlanFor.name}</h3>
              <button onClick={() => { setChangePlanFor(null); setSelectedPlan('') }} className="text-gray-400 hover:text-gray-600 text-2xl">&times;</button>
            </div>
            <div className="p-6 space-y-4">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-sm text-gray-600">Plan actual:</p>
                <p className="font-bold text-gray-900">{changePlanFor.plan_name || 'Free'} ({changePlanFor.active_employees} empleados, ${changePlanFor.plan_price || 0} USD/mes)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Nuevo plan</label>
                <div className="space-y-2">
                  {plans.map(plan => {
                    const isCurrent = changePlanFor.plan_id === plan.id
                    const canFit = changePlanFor.active_employees <= plan.max_employees
                    return (
                      <label
                        key={plan.id}
                        className={`flex items-center gap-3 p-3 rounded-lg border-2 cursor-pointer transition ${
                          isCurrent
                            ? 'border-blue-500 bg-blue-50'
                            : !canFit
                            ? 'border-gray-200 bg-gray-50 opacity-50 cursor-not-allowed'
                            : 'border-gray-200 hover:border-blue-300'
                        }`}
                      >
                        <input
                          type="radio"
                          name="plan-select"
                          value={plan.id}
                          checked={selectedPlan === plan.id}
                          onChange={() => canFit && setSelectedPlan(plan.id)}
                          disabled={!canFit}
                          className="w-4 h-4 text-blue-600"
                        />
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-gray-900">{plan.name}</span>
                            <span className="font-bold text-gray-900">${plan.price_monthly} USD/mes</span>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-gray-500 mt-1">
                            <span>{plan.max_employees} empleados</span>
                            <span>{plan.max_geofences} geocercas</span>
                            {plan.ai_chat && <span>IA ✅</span>}
                            {plan.webhooks && <span>Webhooks ✅</span>}
                          </div>
                        </div>
                      </label>
                    )
                  })}
                </div>
              </div>

              {selectedPlan && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                  <p className="text-xs text-amber-700">
                    ⚠️ El cambio de plan surte efecto inmediatamente. Se actualizará la suscripción y los límites de la empresa.
                  </p>
                </div>
              )}

              <div className="flex gap-3">
                <button onClick={() => { setChangePlanFor(null); setSelectedPlan('') }} className="flex-1 py-2.5 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition">
                  Cancelar
                </button>
                <button
                  onClick={() => handlePlanChange(changePlanFor)}
                  disabled={actionLoading === `${changePlanFor.id}-plan` || !selectedPlan}
                  className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  {actionLoading === `${changePlanFor.id}-plan` ? 'Aplicando...' : 'Aplicar cambio'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Company Modal with Safety Confirmation */}
      {companyToDelete && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden border border-red-100">
            <div className="p-6 bg-gradient-to-r from-red-600 to-rose-700 text-white flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">⚠️</span>
                <div>
                  <h3 className="font-bold text-lg">Eliminar Empresa</h3>
                  <p className="text-xs text-red-100">Acción crítica de super-administrador</p>
                </div>
              </div>
              <button
                onClick={() => { setCompanyToDelete(null); setDeleteConfirmText('') }}
                className="text-white/70 hover:text-white text-2xl"
              >
                &times;
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-xs text-red-800 space-y-2">
                <p className="font-semibold text-sm">¿Estás seguro de eliminar "{companyToDelete.name}"?</p>
                <ul className="list-disc list-inside space-y-1 text-red-700">
                  <li>La empresa será dada de baja en el sistema.</li>
                  <li>Todos los empleados y administradores quedarán desactivados.</li>
                  <li>La suscripción quedará cancelada de inmediato.</li>
                </ul>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                  Para confirmar, escribe <span className="font-mono text-red-600 font-bold">ELIMINAR</span> a continuación:
                </label>
                <input
                  type="text"
                  value={deleteConfirmText}
                  onChange={e => setDeleteConfirmText(e.target.value)}
                  placeholder="ELIMINAR"
                  className="w-full border-2 border-gray-300 focus:border-red-500 rounded-xl px-4 py-2.5 text-sm font-mono text-center tracking-widest uppercase focus:outline-none"
                  autoFocus
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => { setCompanyToDelete(null); setDeleteConfirmText('') }}
                  className="flex-1 py-2.5 border border-gray-300 rounded-xl text-gray-700 font-medium hover:bg-gray-50 transition text-sm"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  disabled={deleteConfirmText.trim().toUpperCase() !== 'ELIMINAR' || actionLoading === `delete-${companyToDelete.id}`}
                  onClick={handleDeleteCompany}
                  className="flex-1 py-2.5 bg-red-600 text-white rounded-xl font-bold hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed transition text-sm shadow-md shadow-red-500/20"
                >
                  {actionLoading === `delete-${companyToDelete.id}` ? 'Eliminando...' : 'Confirmar Eliminación'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

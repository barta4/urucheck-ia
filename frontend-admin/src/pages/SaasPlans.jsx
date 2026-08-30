import { useState, useEffect } from 'react'
import { useToast } from '../context/ToastContext'
import api from '../api'

const ALL_FEATURES = [
  ['face_verification', 'Reconocimiento facial'],
  ['webhooks', 'Webhooks'],
  ['ai_chat', 'Chat IA (Gemini)'],
  ['export_reports', 'Exportar reportes Excel/CSV'],
  ['priority_support', 'Soporte prioritario'],
  ['custom_branding', 'Marca personalizada'],
  ['api_access', 'API personalizada'],
]

export default function SaasPlans() {
  const { success, error: showError } = useToast()
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)      // plan being edited
  const [creating, setCreating] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [form, setForm] = useState(defaultForm())

  useEffect(() => { load() }, [])

  const load = async () => {
    try {
      const res = await api.get('/plans/all')
      setPlans(res.data)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  const openEdit = (plan) => {
    setEditing(plan)
    setForm({
      name: plan.name, slug: plan.slug, description: plan.description || '',
      price_monthly: plan.price_monthly || 0, price_yearly: plan.price_yearly || 0,
      max_employees: plan.max_employees || 10, max_geofences: plan.max_geofences || 2,
      face_verification: plan.face_verification, webhooks: plan.webhooks,
      ai_chat: plan.ai_chat, export_reports: plan.export_reports,
      priority_support: plan.priority_support, custom_branding: plan.custom_branding,
      api_access: plan.api_access, trial_days: plan.trial_days || 14,
    })
  }

  const openCreate = () => {
    setCreating(true)
    setForm(defaultForm())
  }

  const handleSave = async (e) => {
    e.preventDefault()
    try {
      if (editing) {
        await api.patch(`/plans/${editing.id}`, form)
        success('Plan actualizado exitosamente')
      } else {
        await api.post('/plans/', form)
        success('Plan creado exitosamente')
      }
      closeForm()
      load()
    } catch (err) { showError(err.response?.data?.detail || 'Error al guardar') }
  }

  const handleDelete = async () => {
    try {
      await api.delete(`/plans/${confirmDelete.id}`)
      success('Plan eliminado')
      setConfirmDelete(null)
      load()
    } catch (err) { showError(err.response?.data?.detail || 'Error al eliminar') }
  }

  const toggleActive = async (plan) => {
    try {
      await api.patch(`/plans/${plan.id}`, { active: !plan.active })
      success(plan.active ? 'Plan desactivado' : 'Plan activado')
      load()
    } catch (err) { showError(err.response?.data?.detail || 'Error') }
  }

  const closeForm = () => {
    setEditing(null)
    setCreating(false)
    setForm(defaultForm())
  }

  if (loading) return <div className="p-6 text-gray-400">Cargando planes...</div>

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">📦 Gestión de Planes</h2>
          <p className="text-gray-500 text-sm mt-1">Define los planes, precios y features disponibles</p>
        </div>
        <button onClick={openCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
          + Nuevo plan
        </button>
      </div>

      {/* Plans table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-4 py-3 text-left">Plan</th>
              <th className="px-4 py-3 text-left">Precio</th>
              <th className="px-4 py-3 text-left">Límites</th>
              <th className="px-4 py-3 text-left">Trial</th>
              <th className="px-4 py-3 text-left">Features</th>
              <th className="px-4 py-3 text-left">Estado</th>
              <th className="px-4 py-3 text-left">Empresas</th>
              <th className="px-4 py-3 text-left">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {plans.map(plan => (
              <tr key={plan.id} className={`hover:bg-gray-50 ${!plan.active ? 'opacity-50' : ''}`}>
                <td className="px-4 py-3">
                  <p className="font-semibold text-gray-900">{plan.name}</p>
                  <p className="text-xs text-gray-400 font-mono">{plan.slug}</p>
                </td>
                <td className="px-4 py-3">
                  <p className="font-bold text-gray-900">${plan.price_monthly}<span className="text-xs font-normal text-gray-400"> USD/mes</span></p>
                  <p className="text-xs text-gray-400">${plan.price_yearly} USD/año</p>
                </td>
                <td className="px-4 py-3">
                  <p className="text-sm">{plan.max_employees} empleados</p>
                  <p className="text-sm text-gray-400">{plan.max_geofences} geocercas</p>
                </td>
                <td className="px-4 py-3">
                  <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs font-medium">
                    {plan.trial_days} días
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1 max-w-[200px]">
                    {plan.face_verification && <FeatureBadge label="Face" />}
                    {plan.webhooks && <FeatureBadge label="Webhooks" />}
                    {plan.ai_chat && <FeatureBadge label="IA" />}
                    {plan.export_reports && <FeatureBadge label="Export" />}
                    {plan.priority_support && <FeatureBadge label="Soporte" />}
                    {plan.custom_branding && <FeatureBadge label="Branding" />}
                    {plan.api_access && <FeatureBadge label="API" />}
                    {!plan.face_verification && !plan.webhooks && !plan.ai_chat && !plan.export_reports && !plan.priority_support && !plan.custom_branding && !plan.api_access && (
                      <span className="text-xs text-gray-400">Sin features extras</span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <button onClick={() => toggleActive(plan)} className={`px-2 py-1 rounded text-xs font-medium transition ${plan.active ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}>
                    {plan.active ? '✅ Activo' : '⏸️ Inactivo'}
                  </button>
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm font-medium text-gray-700">{plan.company_count || 0}</span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    <button onClick={() => openEdit(plan)} className="px-2 py-1 bg-yellow-50 text-yellow-700 rounded text-xs hover:bg-yellow-100">
                      ✏️ Editar
                    </button>
                    <button onClick={() => setConfirmDelete(plan)} className="px-2 py-1 bg-red-50 text-red-600 rounded text-xs hover:bg-red-100">
                      🗑️
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Edit/Create Modal */}
      {(editing || creating) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b sticky top-0 bg-white z-10">
              <h3 className="font-semibold text-lg">{editing ? `✏️ Editar: ${editing.name}` : '➕ Nuevo Plan'}</h3>
              <button onClick={closeForm} className="text-gray-400 hover:text-gray-600 text-2xl">&times;</button>
            </div>
            <form onSubmit={handleSave} className="p-6 space-y-5">
              {/* Name + Slug */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nombre *</label>
                  <input required value={form.name} onChange={e => setForm({...form, name: e.target.value})} className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Pro" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Slug *</label>
                  <input required value={form.slug} onChange={e => setForm({...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '')})} className="w-full border rounded-lg px-3 py-2 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="pro" />
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Descripción</label>
                <input value={form.description} onChange={e => setForm({...form, description: e.target.value})} className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Hasta 50 empleados con todas las funciones" />
              </div>

              {/* Prices */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Precio mensual ($ USD)</label>
                  <input type="number" min="0" step="0.01" value={form.price_monthly} onChange={e => setForm({...form, price_monthly: parseFloat(e.target.value) || 0})} className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Precio anual ($ USD) <span className="text-gray-400 font-normal">(ahorro sugerido: -17%)</span></label>
                  <input type="number" min="0" step="0.01" value={form.price_yearly} onChange={e => setForm({...form, price_yearly: parseFloat(e.target.value) || 0})} className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>

              {/* Limits */}
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Máx empleados</label>
                  <input type="number" min="1" value={form.max_employees} onChange={e => setForm({...form, max_employees: parseInt(e.target.value) || 10})} className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Máx geocercas</label>
                  <input type="number" min="1" value={form.max_geofences} onChange={e => setForm({...form, max_geofences: parseInt(e.target.value) || 2})} className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Días de trial</label>
                  <input type="number" min="0" max="365" value={form.trial_days} onChange={e => setForm({...form, trial_days: parseInt(e.target.value) || 0})} className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>

              {/* Features checkboxes */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Features incluidas</label>
                <div className="grid grid-cols-2 gap-2">
                  {ALL_FEATURES.map(([key, label]) => (
                    <label key={key} className="flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition select-none hover:bg-gray-50">
                      <input type="checkbox" checked={form[key]} onChange={e => setForm({...form, [key]: e.target.checked})} className="w-4 h-4 text-blue-600 rounded" />
                      <span className="text-sm text-gray-700">{label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Submit */}
              <div className="flex gap-3 pt-4 border-t">
                <button type="submit" className="flex-1 bg-blue-600 text-white rounded-lg py-2.5 font-medium hover:bg-blue-700 transition">
                  {editing ? '💾 Guardar cambios' : '➕ Crear plan'}
                </button>
                <button type="button" onClick={closeForm} className="px-6 py-2.5 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition">
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 text-center">
            <p className="text-4xl mb-4">⚠️</p>
            <h3 className="text-lg font-bold text-gray-900 mb-2">¿Eliminar plan "{confirmDelete.name}"?</h3>
            {confirmDelete.company_count > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
                <p className="text-sm text-red-700 font-medium">
                  ⚠️ {confirmDelete.company_count} empresa(s) usan este plan. Debes reasignarlas primero.
                </p>
              </div>
            )}
            <div className="flex gap-3 mt-4">
              <button onClick={() => setConfirmDelete(null)} className="flex-1 py-2.5 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition">
                Cancelar
              </button>
              <button onClick={handleDelete} disabled={confirmDelete.company_count > 0} className="flex-1 py-2.5 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition">
                Eliminar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function defaultForm() {
  return {
    name: '', slug: '', description: '',
    price_monthly: 0, price_yearly: 0,
    max_employees: 10, max_geofences: 2, trial_days: 14,
    face_verification: true, webhooks: false, ai_chat: false,
    export_reports: true, priority_support: false, custom_branding: false, api_access: false,
  }
}

function FeatureBadge({ label }) {
  return <span className="px-2 py-0.5 bg-green-50 text-green-700 rounded text-[10px] font-medium">{label}</span>
}

import { useState, useEffect } from 'react'
import { useToast } from '../context/ToastContext'
import api from '../api'

const STATUS_BADGES = {
  up_to_date: { label: 'Al día', color: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  trial: { label: 'En Trial', color: 'bg-amber-100 text-amber-800 border-amber-200' },
  overdue: { label: 'Vencido', color: 'bg-rose-100 text-rose-800 border-rose-200' },
  suspended: { label: 'Suspendido', color: 'bg-red-100 text-red-800 border-red-200' },
  cancelled: { label: 'Cancelado', color: 'bg-gray-100 text-gray-600 border-gray-200' },
}

const METHOD_LABELS = {
  mercado_pago: { label: 'MercadoPago', icon: '💳', bg: 'bg-sky-50 text-sky-700' },
  card: { label: 'Tarjeta (MP)', icon: '💳', bg: 'bg-sky-50 text-sky-700' },
  bank_transfer: { label: 'Transferencia', icon: '🏦', bg: 'bg-purple-50 text-purple-700' },
  cash: { label: 'Efectivo', icon: '💵', bg: 'bg-emerald-50 text-emerald-700' },
  check: { label: 'Cheque', icon: '📄', bg: 'bg-orange-50 text-orange-700' },
  crypto: { label: 'Cripto', icon: '🪙', bg: 'bg-amber-50 text-amber-700' },
  other: { label: 'Otro', icon: '📝', bg: 'bg-gray-50 text-gray-700' },
}

export default function SaasBilling() {
  const { success, error: showError, warning } = useToast()
  const [activeTab, setActiveTab] = useState('companies') // 'companies' | 'history'
  const [loading, setLoading] = useState(true)
  const [billingData, setBillingData] = useState(null)
  const [paymentsHistory, setPaymentsHistory] = useState([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historySearch, setHistorySearch] = useState('')
  const [companyFilter, setCompanyFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  // Modals
  const [manualPayCompany, setManualPayCompany] = useState(null)
  const [manualForm, setManualForm] = useState({
    amount: '',
    currency: 'USD',
    method: 'bank_transfer',
    days_to_add: 30,
    notes: '',
  })
  const [paymentLinkCompany, setPaymentLinkCompany] = useState(null)
  const [linkForm, setLinkForm] = useState({ amount: '', description: '' })
  const [generatedLink, setGeneratedLink] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadBilling()
    loadHistory()
  }, [])

  const loadBilling = async () => {
    setLoading(true)
    try {
      const res = await api.get('/saas-metrics/billing')
      setBillingData(res.data)
    } catch (err) {
      console.error(err)
      showError('Error al cargar datos de facturación')
    } finally {
      setLoading(false)
    }
  }

  const loadHistory = async (search = historySearch) => {
    try {
      const res = await api.get('/saas-metrics/payments-history', {
        params: { search: search || undefined, limit: 100 }
      })
      setPaymentsHistory(res.data.payments)
      setHistoryTotal(res.data.total)
    } catch (err) {
      console.error(err)
    }
  }

  const handleManualPayment = async (e) => {
    e.preventDefault()
    if (!manualForm.amount || parseFloat(manualForm.amount) <= 0) {
      return warning('Ingresa un monto válido en USD')
    }
    setSubmitting(true)
    try {
      const res = await api.post('/saas-metrics/manual-payment', {
        company_id: manualPayCompany.company_id,
        amount: parseFloat(manualForm.amount),
        currency: 'USD',
        method: manualForm.method,
        days_to_add: parseInt(manualForm.days_to_add),
        notes: manualForm.notes,
      })
      success(res.data.message || 'Pago registrado exitosamente')
      setManualPayCompany(null)
      loadBilling()
      loadHistory()
    } catch (err) {
      showError(err.response?.data?.detail || 'Error al registrar pago manual')
    } finally {
      setSubmitting(false)
    }
  }

  const handleGeneratePaymentLink = async (e) => {
    e.preventDefault()
    if (!linkForm.amount || parseFloat(linkForm.amount) <= 0) {
      return warning('Ingresa un monto válido')
    }
    setSubmitting(true)
    try {
      const res = await api.post('/saas-metrics/create-payment-link', {
        company_id: paymentLinkCompany.company_id,
        amount: parseFloat(linkForm.amount),
        description: linkForm.description || `Suscripción UruCheck IA - ${paymentLinkCompany.company_name}`,
      })
      setGeneratedLink(res.data.init_point)
      success('Link de pago generado con éxito')
    } catch (err) {
      showError(err.response?.data?.detail || 'Error al generar link de MercadoPago')
    } finally {
      setSubmitting(false)
    }
  }

  const exportCSV = () => {
    if (paymentsHistory.length === 0) return warning('No hay registros para exportar')
    const headers = ['Fecha', 'Empresa', 'Factura', 'Monto USD', 'Método', 'Estado MP', 'ID MP', 'Notas']
    const rows = paymentsHistory.map(p => [
      p.created_at ? new Date(p.created_at).toLocaleString('es') : '',
      p.company_name,
      p.invoice_number || '',
      p.amount,
      p.method,
      p.mercado_pago_status,
      p.mercado_pago_id || '',
      `"${(p.notes || '').replace(/"/g, '""')}"`
    ])
    const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `historial_pagos_urucheck_${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  if (loading) return <div className="p-8 text-gray-400 font-medium">Cargando estado financiero...</div>

  const { companies = [], summary = {} } = billingData || {}

  const filteredCompanies = (Array.isArray(companies) ? companies : []).filter(c => {
    if (companyFilter && !c.company_name.toLowerCase().includes(companyFilter.toLowerCase()) && !c.company_slug.includes(companyFilter.toLowerCase())) return false
    if (statusFilter && c.billing_status !== statusFilter) return false
    return true
  })

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-gray-900">💳 Cobros y Facturación SaaS</h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-blue-100 text-blue-800 tracking-wider">
              USD
            </span>
          </div>
          <p className="text-gray-500 text-xs sm:text-sm mt-1">
            Supervisa el estado de pagos de cada empresa, cobra suscripciones y gestiona transacciones globales.
          </p>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center bg-gray-200/80 p-1 rounded-xl shrink-0">
          <button
            onClick={() => setActiveTab('companies')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition ${
              activeTab === 'companies'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            🏢 Estado por Empresa
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition ${
              activeTab === 'history'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            📋 Historial Global ({historyTotal})
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl p-5 border border-emerald-100 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Total Recaudado</span>
            <span className="p-2.5 bg-emerald-50 text-emerald-600 rounded-xl text-lg">💰</span>
          </div>
          <p className="text-3xl font-extrabold text-emerald-600 mt-2">${summary.total_collected?.toLocaleString() || '0'}</p>
          <p className="text-xs text-gray-400 mt-1">Acumulado histórico total (USD)</p>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-blue-100 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">MRR Activo</span>
            <span className="p-2.5 bg-blue-50 text-blue-600 rounded-xl text-lg">📈</span>
          </div>
          <p className="text-3xl font-extrabold text-blue-600 mt-2">${summary.mrr?.toLocaleString() || '0'}</p>
          <p className="text-xs text-gray-400 mt-1">Ingreso recurrente mensual (USD)</p>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-purple-100 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Empresas al Día</span>
            <span className="p-2.5 bg-purple-50 text-purple-600 rounded-xl text-lg">✅</span>
          </div>
          <p className="text-3xl font-extrabold text-gray-900 mt-2">{summary.up_to_date || 0} <span className="text-xs text-gray-400 font-normal">/ {summary.total_companies}</span></p>
          <p className="text-xs text-purple-600 font-medium mt-1">{summary.in_trial || 0} en período de prueba</p>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-rose-100 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Por Cobrar / Vencidas</span>
            <span className="p-2.5 bg-rose-50 text-rose-600 rounded-xl text-lg">⚠️</span>
          </div>
          <p className="text-3xl font-extrabold text-rose-600 mt-2">{summary.overdue || 0}</p>
          <p className="text-xs text-rose-600 font-medium mt-1">${summary.total_pending || '0'} USD pendientes</p>
        </div>
      </div>

      {/* TAB 1: Companies Billing View */}
      {activeTab === 'companies' && (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <div>
                <input
                  type="text"
                  placeholder="Buscar empresa por nombre..."
                  value={companyFilter}
                  onChange={e => setCompanyFilter(e.target.value)}
                  className="border border-gray-200 rounded-xl px-3.5 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <select
                  value={statusFilter}
                  onChange={e => setStatusFilter(e.target.value)}
                  className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Todos los estados</option>
                  <option value="up_to_date">✅ Al día</option>
                  <option value="trial">🧪 En Trial</option>
                  <option value="overdue">⚠️ Vencidos</option>
                  <option value="suspended">⏸️ Suspendidos</option>
                  <option value="cancelled">🚫 Cancelados</option>
                </select>
              </div>
              {(companyFilter || statusFilter) && (
                <button
                  onClick={() => { setCompanyFilter(''); setStatusFilter('') }}
                  className="text-xs text-gray-500 hover:text-gray-800 underline"
                >
                  Limpiar filtros
                </button>
              )}
            </div>

            <div className="text-xs text-gray-400">
              Mostrando {filteredCompanies.length} de {companies.length} empresas
            </div>
          </div>

          {/* Companies Table */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-x-auto">
            <table className="w-full text-sm min-w-[950px]">
              <thead className="bg-gray-50/75 text-gray-600 text-xs uppercase tracking-wider font-semibold border-b border-gray-100">
                <tr>
                  <th className="px-5 py-3.5 text-left">Empresa</th>
                  <th className="px-4 py-3.5 text-left">Plan & Cuota</th>
                  <th className="px-4 py-3.5 text-left">Estado de Cobro</th>
                  <th className="px-4 py-3.5 text-left">Próximo Vencimiento</th>
                  <th className="px-4 py-3.5 text-left">Último Pago</th>
                  <th className="px-4 py-3.5 text-left">Total Cobrado</th>
                  <th className="px-5 py-3.5 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredCompanies.map(c => {
                  const badge = STATUS_BADGES[c.billing_status] || STATUS_BADGES.up_to_date
                  return (
                    <tr key={c.company_id} className="hover:bg-gray-50/60 transition">
                      <td className="px-5 py-4">
                        <p className="font-bold text-gray-900">{c.company_name}</p>
                        <p className="text-xs text-gray-400 font-mono">{c.company_slug}</p>
                        <p className="text-xs text-gray-400">{c.admin_email}</p>
                      </td>
                      <td className="px-4 py-4">
                        <span className="font-bold text-blue-600 text-xs bg-blue-50 px-2.5 py-1 rounded-full">
                          {c.plan_name}
                        </span>
                        <p className="font-extrabold text-gray-900 mt-1">
                          ${c.plan_price} <span className="text-[11px] font-normal text-gray-400">USD/mes</span>
                        </p>
                      </td>
                      <td className="px-4 py-4">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-bold border inline-block ${badge.color}`}>
                          {badge.label}
                        </span>
                        {c.days_overdue > 0 && (
                          <p className="text-xs text-rose-600 font-semibold mt-1">
                            ⚠️ Atrasado {c.days_overdue} {c.days_overdue === 1 ? 'día' : 'días'}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        {c.next_due_date ? (
                          <>
                            <p className="text-xs font-medium text-gray-800">
                              {new Date(c.next_due_date).toLocaleDateString('es', { day: '2-digit', month: 'short', year: 'numeric' })}
                            </p>
                            <p className="text-[11px] text-gray-400">
                              {c.billing_status === 'trial' ? 'Fin de prueba' : 'Renovación'}
                            </p>
                          </>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        {c.last_payment_at ? (
                          <>
                            <p className="font-bold text-gray-900 text-xs">
                              ${c.last_payment_amount} USD
                            </p>
                            <p className="text-[11px] text-gray-400">
                              {new Date(c.last_payment_at).toLocaleDateString('es')} ({c.last_payment_method || 'MP'})
                            </p>
                          </>
                        ) : (
                          <span className="text-xs text-gray-400 italic">Sin pagos previos</span>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        <span className="font-extrabold text-gray-900">${c.total_paid}</span>
                        <span className="text-xs text-gray-400"> USD</span>
                        <p className="text-[11px] text-gray-400">{c.payment_count} {c.payment_count === 1 ? 'transacción' : 'transacciones'}</p>
                      </td>
                      <td className="px-5 py-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => {
                              setManualPayCompany(c)
                              setManualForm({
                                amount: c.plan_price || '29',
                                currency: 'USD',
                                method: 'bank_transfer',
                                days_to_add: 30,
                                notes: '',
                              })
                            }}
                            className="px-3 py-1.5 bg-emerald-50 text-emerald-700 font-semibold rounded-xl text-xs hover:bg-emerald-100 transition inline-flex items-center gap-1 shadow-sm"
                            title="Registrar pago manual"
                          >
                            💳 Registrar Pago
                          </button>
                          <button
                            onClick={() => {
                              setPaymentLinkCompany(c)
                              setLinkForm({
                                amount: c.plan_price || '29',
                                description: `Suscripción UruCheck IA - ${c.company_name}`
                              })
                              setGeneratedLink(null)
                            }}
                            className="px-3 py-1.5 bg-sky-50 text-sky-700 font-semibold rounded-xl text-xs hover:bg-sky-100 transition inline-flex items-center gap-1 shadow-sm"
                            title="Generar link de MercadoPago"
                          >
                            🔗 Link MP
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: Payments History View */}
      {activeTab === 'history' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Buscar por empresa, ID MP o método..."
                value={historySearch}
                onChange={e => {
                  setHistorySearch(e.target.value)
                  loadHistory(e.target.value)
                }}
                className="border border-gray-200 rounded-xl px-3.5 py-2 text-sm w-72 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={exportCSV}
                className="px-4 py-2 bg-gray-900 text-white rounded-xl text-xs font-bold hover:bg-gray-800 transition inline-flex items-center gap-1.5 shadow-sm"
              >
                📥 Exportar Excel (CSV)
              </button>
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-x-auto">
            <table className="w-full text-sm min-w-[900px]">
              <thead className="bg-gray-50/75 text-gray-600 text-xs uppercase tracking-wider font-semibold border-b border-gray-100">
                <tr>
                  <th className="px-5 py-3.5 text-left">Fecha</th>
                  <th className="px-4 py-3.5 text-left">Empresa</th>
                  <th className="px-4 py-3.5 text-left">Factura</th>
                  <th className="px-4 py-3.5 text-left">Monto</th>
                  <th className="px-4 py-3.5 text-left">Método</th>
                  <th className="px-4 py-3.5 text-left">Estado / ID Transacción</th>
                  <th className="px-5 py-3.5 text-left">Notas</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {paymentsHistory.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="px-5 py-12 text-center text-gray-400">
                      No se encontraron transacciones registradas.
                    </td>
                  </tr>
                ) : (
                  paymentsHistory.map(p => {
                    const methodInfo = METHOD_LABELS[p.method] || METHOD_LABELS.other
                    return (
                      <tr key={p.id} className="hover:bg-gray-50/60 transition">
                        <td className="px-5 py-4 text-xs text-gray-500">
                          {p.created_at ? new Date(p.created_at).toLocaleString('es') : '—'}
                        </td>
                        <td className="px-4 py-4">
                          <p className="font-bold text-gray-900">{p.company_name}</p>
                          <p className="text-[11px] text-gray-400 font-mono">{p.company_slug}</p>
                        </td>
                        <td className="px-4 py-4">
                          <span className="font-mono text-xs text-gray-600 bg-gray-100 px-2 py-0.5 rounded">
                            {p.invoice_number || 'S/N'}
                          </span>
                        </td>
                        <td className="px-4 py-4">
                          <span className="font-extrabold text-emerald-600 text-base">${p.amount}</span>
                          <span className="text-xs text-gray-500 font-semibold"> {p.currency || 'USD'}</span>
                        </td>
                        <td className="px-4 py-4">
                          <span className={`px-2.5 py-1 rounded-full text-xs font-bold inline-flex items-center gap-1 ${methodInfo.bg}`}>
                            <span>{methodInfo.icon}</span>
                            <span>{methodInfo.label}</span>
                          </span>
                        </td>
                        <td className="px-4 py-4">
                          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-green-100 text-green-700">
                            {p.mercado_pago_status || 'Aprobado'}
                          </span>
                          {p.mercado_pago_id && (
                            <p className="text-[11px] text-gray-400 font-mono mt-0.5">{p.mercado_pago_id}</p>
                          )}
                        </td>
                        <td className="px-5 py-4 text-xs text-gray-500 max-w-xs truncate">
                          {p.notes || '—'}
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL 1: Registrar Pago Manual */}
      {manualPayCompany && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden border border-emerald-100">
            <div className="p-6 bg-gradient-to-r from-emerald-600 to-teal-700 text-white flex items-center justify-between">
              <div>
                <h3 className="font-bold text-lg">Registrar Pago Manual</h3>
                <p className="text-xs text-emerald-100 mt-0.5">Empresa: {manualPayCompany.company_name}</p>
              </div>
              <button
                onClick={() => setManualPayCompany(null)}
                className="text-white/70 hover:text-white text-2xl"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleManualPayment} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Monto en USD *</label>
                  <div className="relative">
                    <span className="absolute left-3 top-2.5 text-gray-400 font-bold text-sm">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      required
                      value={manualForm.amount}
                      onChange={e => setManualForm({ ...manualForm, amount: e.target.value })}
                      placeholder="29.00"
                      className="w-full border rounded-xl pl-7 pr-3 py-2 text-sm font-bold text-gray-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Método de Cobro</label>
                  <select
                    value={manualForm.method}
                    onChange={e => setManualForm({ ...manualForm, method: e.target.value })}
                    className="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  >
                    <option value="bank_transfer">🏦 Transferencia Bancaria</option>
                    <option value="cash">💵 Efectivo</option>
                    <option value="check">📄 Cheque</option>
                    <option value="card">💳 Tarjeta Externa</option>
                    <option value="crypto">🪙 Cripto</option>
                    <option value="other">📝 Otro</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Extender Suscripción Por</label>
                <select
                  value={manualForm.days_to_add}
                  onChange={e => setManualForm({ ...manualForm, days_to_add: e.target.value })}
                  className="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value={15}>15 días</option>
                  <option value={30}>30 días (1 mes estándar)</option>
                  <option value={60}>60 días (2 meses)</option>
                  <option value={90}>90 días (1 trimestre)</option>
                  <option value={365}>365 días (1 año completo)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Notas / Nro. Comprobante</label>
                <textarea
                  rows="2"
                  value={manualForm.notes}
                  onChange={e => setManualForm({ ...manualForm, notes: e.target.value })}
                  placeholder="Ej: Transferencia BBVA #48291 recibida en fecha..."
                  className="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-xs text-emerald-800">
                ✅ Al confirmar, la empresa pasará inmediatamente a estado <strong>Activo</strong>, se extenderá su fecha de vencimiento y se emitirá la factura correspondiente.
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setManualPayCompany(null)}
                  className="flex-1 py-2.5 border border-gray-300 rounded-xl text-gray-700 font-medium hover:bg-gray-50 text-sm"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 py-2.5 bg-emerald-600 text-white rounded-xl font-bold hover:bg-emerald-700 disabled:opacity-50 text-sm shadow-md shadow-emerald-600/20"
                >
                  {submitting ? 'Procesando...' : 'Confirmar Cobro'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Generar Link de Pago MercadoPago */}
      {paymentLinkCompany && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden border border-sky-100">
            <div className="p-6 bg-gradient-to-r from-sky-600 to-blue-700 text-white flex items-center justify-between">
              <div>
                <h3 className="font-bold text-lg">Link de Pago MercadoPago</h3>
                <p className="text-xs text-sky-100 mt-0.5">Para: {paymentLinkCompany.company_name}</p>
              </div>
              <button
                onClick={() => setPaymentLinkCompany(null)}
                className="text-white/70 hover:text-white text-2xl"
              >
                &times;
              </button>
            </div>

            <div className="p-6 space-y-4">
              {!generatedLink ? (
                <form onSubmit={handleGeneratePaymentLink} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">Monto a Cobrar (USD) *</label>
                    <div className="relative">
                      <span className="absolute left-3 top-2.5 text-gray-400 font-bold text-sm">$</span>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        required
                        value={linkForm.amount}
                        onChange={e => setLinkForm({ ...linkForm, amount: e.target.value })}
                        className="w-full border rounded-xl pl-7 pr-3 py-2 text-sm font-bold text-gray-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">Concepto</label>
                    <input
                      type="text"
                      value={linkForm.description}
                      onChange={e => setLinkForm({ ...linkForm, description: e.target.value })}
                      className="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  <div className="flex gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setPaymentLinkCompany(null)}
                      className="flex-1 py-2.5 border border-gray-300 rounded-xl text-gray-700 font-medium text-sm"
                    >
                      Cancelar
                    </button>
                    <button
                      type="submit"
                      disabled={submitting}
                      className="flex-1 py-2.5 bg-sky-600 text-white rounded-xl font-bold hover:bg-sky-700 disabled:opacity-50 text-sm shadow-md shadow-sky-600/20"
                    >
                      {submitting ? 'Generando...' : 'Generar Link'}
                    </button>
                  </div>
                </form>
              ) : (
                <div className="space-y-4">
                  <div className="bg-sky-50 border border-sky-200 rounded-2xl p-4 text-center">
                    <p className="text-2xl mb-1">🎉</p>
                    <p className="font-bold text-sky-900 text-sm">¡Link de MercadoPago listo!</p>
                    <p className="text-xs text-sky-700 mt-1">
                      Copia este enlace y envíaselo al cliente por WhatsApp, Email o mensaje directo:
                    </p>
                    <input
                      readOnly
                      value={generatedLink}
                      onClick={e => e.target.select()}
                      className="mt-3 w-full bg-white border border-sky-300 rounded-xl px-3 py-2 text-xs font-mono text-gray-700 text-center"
                    />
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(generatedLink)
                        success('Link copiado al portapapeles')
                      }}
                      className="flex-1 py-2.5 bg-sky-600 text-white rounded-xl font-bold hover:bg-sky-700 text-sm shadow-sm"
                    >
                      📋 Copiar Enlace
                    </button>
                    <a
                      href={generatedLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2.5 border border-sky-300 text-sky-700 rounded-xl font-bold hover:bg-sky-50 text-sm inline-flex items-center"
                    >
                      Abrir ↗
                    </a>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

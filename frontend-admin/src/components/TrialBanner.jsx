import { useState, useEffect } from 'react'
import { Sparkles, Clock, Check, ArrowRight, X, ShieldCheck } from 'lucide-react'
import api from '../api'
import { useToast } from '../context/ToastContext'

export default function TrialBanner() {
  const { success, error: showError } = useToast()
  const [sub, setSub] = useState(null)
  const [showUpgradeModal, setShowUpgradeModal] = useState(false)
  const [plans, setPlans] = useState([])
  const [loadingPlans, setLoadingPlans] = useState(false)
  const [selectedPlanId, setSelectedPlanId] = useState(null)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    api.get('/subscriptions/my')
      .then(res => setSub(res.data))
      .catch(() => {})
  }, [])

  const openModal = async () => {
    setShowUpgradeModal(true)
    setLoadingPlans(true)
    try {
      const res = await api.get('/plans/')
      setPlans(Array.isArray(res.data) ? res.data.filter(p => p.active) : [])
    } catch (e) {
      showError('Error al cargar planes disponibles')
    } finally {
      setLoadingPlans(false)
    }
  }

  const handleSelectPlan = async (planId) => {
    setSelectedPlanId(planId)
    try {
      await api.post('/subscriptions/change-plan', { plan_id: planId })
      success('Plan actualizado con éxito. ¡Gracias por confiar en UruCheck IA!')
      setShowUpgradeModal(false)
      const res = await api.get('/subscriptions/my')
      setSub(res.data)
    } catch (e) {
      showError(e.response?.data?.detail || 'Error al procesar la actualización del plan')
    }
  }

  if (!sub || !sub.is_trial_active || dismissed) return null

  const days = sub.trial_remaining_days

  return (
    <>
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 text-white px-4 py-2 text-xs sm:text-sm font-medium flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-2 mx-auto">
          <Clock className="w-4 h-4 text-amber-100 shrink-0" />
          <span>
            Estás usando el <strong>Período de Prueba ({sub.plan_name || 'Pro'})</strong> — Te quedan{' '}
            <strong className="underline underline-offset-2">{days} {days === 1 ? 'día' : 'días'}</strong> de acceso completo.
          </span>
          <button
            onClick={openModal}
            className="ml-3 bg-white text-orange-700 px-3 py-0.5 rounded-full text-xs font-bold hover:bg-amber-50 shadow-sm transition inline-flex items-center gap-1"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Mejorar Plan
          </button>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-amber-100 hover:text-white p-1 rounded-lg transition"
          title="Ocultar aviso por ahora"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Upgrade Modal */}
      {showUpgradeModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-gray-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl shadow-2xl max-w-4xl w-full overflow-hidden border border-gray-100">
            <div className="p-6 bg-gradient-to-br from-blue-900 via-indigo-900 to-slate-900 text-white flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 text-amber-400 font-semibold text-xs uppercase tracking-wider">
                  <ShieldCheck className="w-4 h-4" />
                  Suscripción UruCheck IA SaaS
                </div>
                <h3 className="text-xl font-bold mt-1">Elige el plan ideal para tu empresa</h3>
                <p className="text-sm text-blue-200 mt-0.5">Control de asistencia biométrico, reportes y cumplimiento garantizado.</p>
              </div>
              <button
                onClick={() => setShowUpgradeModal(false)}
                className="text-white/70 hover:text-white p-2 rounded-xl bg-white/10 hover:bg-white/20 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 sm:p-8">
              {loadingPlans ? (
                <div className="text-center py-12 text-gray-500 text-sm">Cargando planes...</div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {plans.map(plan => {
                    const isCurrent = sub.plan_slug === plan.slug
                    return (
                      <div
                        key={plan.id}
                        className={`rounded-2xl p-6 border flex flex-col justify-between transition-all ${
                          isCurrent
                            ? 'border-blue-600 bg-blue-50/40 ring-2 ring-blue-600/20 shadow-md'
                            : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-lg'
                        }`}
                      >
                        <div>
                          <div className="flex items-center justify-between">
                            <h4 className="font-bold text-gray-900 text-lg">{plan.name}</h4>
                            {isCurrent && (
                              <span className="text-[11px] font-bold text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full">
                                Actual
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 mt-1 min-h-[32px]">{plan.description}</p>

                          <div className="mt-4 mb-5">
                            <span className="text-3xl font-extrabold text-gray-900">
                              ${plan.price_monthly}
                            </span>
                            <span className="text-xs text-gray-500"> /mes</span>
                          </div>

                          <div className="space-y-2.5 text-xs text-gray-600 pt-4 border-t border-gray-100">
                            <div className="flex items-center gap-2">
                              <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                              <span>Hasta <strong>{plan.max_employees}</strong> empleados</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                              <span>Hasta <strong>{plan.max_geofences}</strong> geocercas</span>
                            </div>
                            {plan.face_verification && (
                              <div className="flex items-center gap-2">
                                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                                <span>Verificación Facial IA</span>
                              </div>
                            )}
                            {plan.export_reports && (
                              <div className="flex items-center gap-2">
                                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                                <span>Exportación PDF con QR</span>
                              </div>
                            )}
                          </div>
                        </div>

                        <button
                          disabled={isCurrent}
                          onClick={() => handleSelectPlan(plan.id)}
                          className={`mt-6 w-full py-2.5 rounded-xl font-semibold text-xs flex items-center justify-center gap-2 transition ${
                            isCurrent
                              ? 'bg-gray-100 text-gray-400 cursor-default'
                              : 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm'
                          }`}
                        >
                          {isCurrent ? 'Plan Actual' : 'Seleccionar Plan'}
                          {!isCurrent && <ArrowRight className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

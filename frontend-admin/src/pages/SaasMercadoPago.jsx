import { useState, useEffect } from 'react'
import { useToast } from '../context/ToastContext'
import api from '../api'

export default function SaasMercadoPago() {
  const { success, error: showError, warning } = useToast()
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState(null)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showSecrets, setShowSecrets] = useState(false)

  const [form, setForm] = useState({
    client_id: '',
    client_secret: '',
    access_token: '',
    public_key: '',
  })

  useEffect(() => {
    loadStatus()
  }, [])

  const loadStatus = async () => {
    setLoading(true)
    try {
      const res = await api.get('/saas-metrics/mercadopago/status')
      setStatus(res.data)
      setForm(prev => ({
        ...prev,
        client_id: res.data.client_id || '',
        public_key: res.data.public_key || '',
      }))
    } catch (err) {
      console.error(err)
      showError('Error al cargar estado de MercadoPago')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api.post('/saas-metrics/mercadopago/credentials', form)
      success('Credenciales guardadas con éxito en el servidor')
      await loadStatus()
    } catch (err) {
      showError(err.response?.data?.detail || 'Error al guardar credenciales')
    } finally {
      setSaving(false)
    }
  }

  const handleTestConnection = async () => {
    setTesting(true)
    try {
      const res = await api.post('/saas-metrics/mercadopago/test')
      if (res.data.success) {
        success(`¡Conexión exitosa con MercadoPago! Cuenta: ${res.data.account?.email || res.data.account?.nickname}`)
        await loadStatus()
      }
    } catch (err) {
      showError(err.response?.data?.detail || 'Error probando la conexión con MercadoPago. Revisa el Access Token.')
    } finally {
      setTesting(false)
    }
  }

  if (loading) return <div className="p-8 text-gray-400 font-medium">Cargando integración de MercadoPago...</div>

  const isConnected = status?.token_valid === true
  const hasToken = status?.has_access_token
  const account = status?.account_info

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold text-gray-900">🔗 Conexión e Integración con MercadoPago</h2>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-sky-100 text-sky-800">
            Checkout Pro & Subscripciones
          </span>
        </div>
        <p className="text-gray-500 text-sm mt-1">
          Configura las credenciales de tu cuenta de MercadoPago / MercadoLibre para cobrar suscripciones automáticamente y procesar pagos en USD.
        </p>
      </div>

      {/* Connection Status Banner Card */}
      <div className={`rounded-3xl p-6 border shadow-sm transition-all ${
        isConnected
          ? 'bg-gradient-to-r from-emerald-900 via-teal-900 to-slate-900 text-white border-emerald-500/30'
          : hasToken
          ? 'bg-gradient-to-r from-amber-900 via-orange-900 to-slate-900 text-white border-amber-500/30'
          : 'bg-gradient-to-r from-slate-900 via-gray-900 to-blue-950 text-white border-gray-800'
      }`}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className={`p-4 rounded-2xl shrink-0 text-3xl ${
              isConnected ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/10 text-white'
            }`}>
              {isConnected ? '🟢' : hasToken ? '🟡' : '🔴'}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-xl font-extrabold">
                  {isConnected
                    ? 'MercadoPago Conectado y Verificado'
                    : hasToken
                    ? 'Token Configurado (Pendiente de Verificación)'
                    : 'MercadoPago No Configurado'}
                </h3>
              </div>
              <p className="text-xs sm:text-sm text-gray-300 mt-1">
                {isConnected
                  ? 'El sistema está recibiendo y procesando cobros de suscripciones automáticamente.'
                  : 'Ingresa tu Access Token o credenciales OAuth para habilitar cobros en línea.'}
              </p>

              {account && (
                <div className="mt-4 flex flex-wrap items-center gap-4 text-xs bg-white/10 px-4 py-2.5 rounded-xl border border-white/10">
                  <div>
                    <span className="text-gray-400">Titular:</span>{' '}
                    <strong className="text-white">{account.nickname || account.email}</strong>
                  </div>
                  <div>
                    <span className="text-gray-400">Email:</span>{' '}
                    <strong className="text-white">{account.email}</strong>
                  </div>
                  <div>
                    <span className="text-gray-400">Sitio / País:</span>{' '}
                    <strong className="text-white">{account.site_id || 'MLU'} ({account.country_id || 'UY'})</strong>
                  </div>
                  <div>
                    <span className="text-gray-400">Moneda:</span>{' '}
                    <strong className="text-emerald-400">USD</strong>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="flex sm:flex-col gap-2 shrink-0">
            <button
              onClick={handleTestConnection}
              disabled={testing || (!hasToken && !form.access_token)}
              className="px-5 py-2.5 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed text-gray-950 font-bold rounded-xl text-xs transition flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20"
            >
              {testing ? '⏳ Verificando...' : '⚡ Probar Conexión'}
            </button>
          </div>
        </div>
      </div>

      {/* Credentials Form */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-gray-100 space-y-6">
        <div className="flex items-center justify-between border-b border-gray-100 pb-4">
          <div>
            <h3 className="font-bold text-lg text-gray-900">🔑 Credenciales de la Aplicación</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Obtén estas claves en el <a href="https://www.mercadopago.com/developers/panel/app" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline font-semibold">Panel de Desarrolladores de MercadoPago</a>.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowSecrets(!showSecrets)}
            className="text-xs font-semibold text-gray-600 bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded-xl transition"
          >
            {showSecrets ? '🙈 Ocultar secretos' : '👁️ Mostrar secretos'}
          </button>
        </div>

        <form onSubmit={handleSave} className="space-y-5">
          {/* Access Token */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                Access Token de Producción (Recomendado) *
              </label>
              <span className="text-[11px] text-gray-400">Inicia con <code className="bg-gray-100 px-1 rounded text-blue-600">APP_USR-...</code></span>
            </div>
            <input
              type={showSecrets ? 'text' : 'password'}
              value={form.access_token}
              onChange={e => setForm({ ...form, access_token: e.target.value })}
              placeholder={status?.has_access_token ? '•••••••••••••••••••••••••••••••• (Configurado en el servidor)' : 'APP_USR-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}
              className="w-full border border-gray-300 focus:border-blue-500 rounded-xl px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-gray-500 mt-1">
              Es la clave principal utilizada para generar preferencias de cobro, procesar suscripciones y validar webhooks.
            </p>
          </div>

          {/* Public Key */}
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
              Public Key (Opcional para Frontend)
            </label>
            <input
              type="text"
              value={form.public_key}
              onChange={e => setForm({ ...form, public_key: e.target.value })}
              placeholder="APP_USR-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="w-full border border-gray-300 focus:border-blue-500 rounded-xl px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            {/* Client ID */}
            <div>
              <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                Client ID (Para flujo OAuth)
              </label>
              <input
                type="text"
                value={form.client_id}
                onChange={e => setForm({ ...form, client_id: e.target.value })}
                placeholder="1234567890123456"
                className="w-full border border-gray-300 focus:border-blue-500 rounded-xl px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              />
            </div>

            {/* Client Secret */}
            <div>
              <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                Client Secret
              </label>
              <input
                type={showSecrets ? 'text' : 'password'}
                value={form.client_secret}
                onChange={e => setForm({ ...form, client_secret: e.target.value })}
                placeholder={status?.has_client_secret ? '••••••••••••••••' : 'Client secret de tu app'}
                className="w-full border border-gray-300 focus:border-blue-500 rounded-xl px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              />
            </div>
          </div>

          <div className="pt-4 flex items-center justify-between border-t border-gray-100">
            <p className="text-xs text-gray-500">
              💡 Los cambios se aplican de forma inmediata sin necesidad de reiniciar el backend.
            </p>
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold rounded-xl text-sm transition shadow-md shadow-blue-500/20"
            >
              {saving ? 'Guardando...' : '💾 Guardar Credenciales'}
            </button>
          </div>
        </form>
      </div>

      {/* Integration Instructions & Webhook Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-3xl p-6 shadow-sm border border-gray-100 space-y-3">
          <h4 className="font-bold text-gray-900 text-sm flex items-center gap-2">
            <span>📡</span> URL de Webhook para Notificaciones IPN
          </h4>
          <p className="text-xs text-gray-600 leading-relaxed">
            Configura esta URL en tu panel de MercadoPago para que las suscripciones pagadas se acrediten automáticamente:
          </p>
          <div className="bg-gray-50 p-3 rounded-xl border border-gray-200 font-mono text-xs text-blue-700 break-all select-all">
            {window.location.origin.replace('http://', 'https://')}/api/payments/webhook
          </div>
          <p className="text-[11px] text-gray-400">
            Eventos a suscribir: <code>payment</code>, <code>subscription_preapproval</code>.
          </p>
        </div>

        <div className="bg-white rounded-3xl p-6 shadow-sm border border-gray-100 space-y-3">
          <h4 className="font-bold text-gray-900 text-sm flex items-center gap-2">
            <span>🌎</span> Facturación Internacional en USD
          </h4>
          <p className="text-xs text-gray-600 leading-relaxed">
            El sistema emite todas las preferencias de pago en <strong>USD</strong>. MercadoPago realiza la conversión transparente a la moneda local del comprador al momento de pagar con tarjeta de crédito, débito o billetera digital.
          </p>
          <div className="bg-emerald-50 text-emerald-800 text-xs p-3 rounded-xl border border-emerald-200">
            ✅ Compatible con clientes de Uruguay, Argentina, Brasil, México, Chile, Colombia y todo LATAM.
          </div>
        </div>
      </div>
    </div>
  )
}

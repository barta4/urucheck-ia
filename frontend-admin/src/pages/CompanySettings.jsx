import { useState, useEffect, useRef } from 'react'
import { useCompany } from '../context/CompanyContext'
import { useToast } from '../context/ToastContext'
import api from '../api'

const NOTIFY_TOGGLES = [
  { key: 'webhook_notify_checkin', label: '📥 Entrada', description: 'Cuando un empleado marca su llegada' },
  { key: 'webhook_notify_checkout', label: '📤 Salida', description: 'Cuando un empleado marca su salida' },
  { key: 'webhook_notify_break', label: '☕ Descanso', description: 'Cuando inicia o termina un descanso' },
  { key: 'webhook_notify_late', label: '⚠️ Llegada tarde', description: 'Cuando alguien llega después del horario' },
  { key: 'webhook_notify_absence', label: '🚨 Falta / Ausencia', description: 'Cuando el Agente detecta que alguien no llegó' },
]

export default function CompanySettings() {
  const company = useCompany()
  const { success: showSuccess, error: showError } = useToast()
  const [form, setForm] = useState({
    company_name: company.company_name || 'Mi Empresa',
    primary_color: company.primary_color || '#2563eb',
    accent_color: company.accent_color || '#1d4ed8',
    webhook_url: company.webhook_url || '',
    bonus_success_message: company.bonus_success_message || '',
    bonus_pending_message: company.bonus_pending_message || '',
    webhook_notify_checkin: company.webhook_notify_checkin || false,
    webhook_notify_checkout: company.webhook_notify_checkout || false,
    webhook_notify_break: company.webhook_notify_break || false,
    webhook_notify_late: company.webhook_notify_late || false,
    webhook_notify_absence: company.webhook_notify_absence || false,
    face_verification_enabled: company.face_verification_enabled || false,
    face_verification_provider: company.face_verification_provider || 'face_recognition',
    smtp_host: company.smtp_host || '',
    smtp_port: company.smtp_port || 587,
    smtp_username: company.smtp_username || '',
    smtp_password: company.smtp_password || '',
    smtp_from_email: company.smtp_from_email || '',
    smtp_to_email: company.smtp_to_email || '',
    email_notify_monthly_report: company.email_notify_monthly_report || false,
    live_tracking_enabled: company.live_tracking_enabled || false,
    live_tracking_interval_minutes: company.live_tracking_interval_minutes || 15,
  })

  useEffect(() => {
    if (!company.loading) {
      setForm({
        company_name: company.company_name || 'Mi Empresa',
        primary_color: company.primary_color || '#2563eb',
        accent_color: company.accent_color || '#1d4ed8',
        webhook_url: company.webhook_url || '',
        bonus_success_message: company.bonus_success_message || '',
        bonus_pending_message: company.bonus_pending_message || '',
        webhook_notify_checkin: Boolean(company.webhook_notify_checkin),
        webhook_notify_checkout: Boolean(company.webhook_notify_checkout),
        webhook_notify_break: Boolean(company.webhook_notify_break),
        webhook_notify_late: Boolean(company.webhook_notify_late),
        webhook_notify_absence: Boolean(company.webhook_notify_absence),
        face_verification_enabled: Boolean(company.face_verification_enabled),
        face_verification_provider: company.face_verification_provider || 'face_recognition',
        smtp_host: company.smtp_host || '',
        smtp_port: company.smtp_port || 587,
        smtp_username: company.smtp_username || '',
        smtp_password: company.smtp_password || '',
        smtp_from_email: company.smtp_from_email || '',
        smtp_to_email: company.smtp_to_email || '',
        email_notify_monthly_report: Boolean(company.email_notify_monthly_report),
        live_tracking_enabled: Boolean(company.live_tracking_enabled),
        live_tracking_interval_minutes: company.live_tracking_interval_minutes || 15,
      })
    }
  }, [company])
  const [logoFile, setLogoFile] = useState(null)
  const [logoPreview, setLogoPreview] = useState(null)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)
  const [testStatus, setTestStatus] = useState(null) // null | 'loading' | 'ok' | 'error'
  const [testMsg, setTestMsg] = useState('')
  const [emailSending, setEmailSending] = useState(false)
  const [emailTestStatus, setEmailTestStatus] = useState(null) // null | 'ok' | 'error'
  const [emailTestMsg, setEmailTestMsg] = useState('')
  const fileRef = useRef()

  const handleLogoChange = (e) => {
    const file = e.target.files[0]
    if (!file) return
    setLogoFile(file)
    setLogoPreview(URL.createObjectURL(file))
  }

  const handleToggle = (key) => {
    setForm(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const handleSave = async (e) => {
    if (e) e.preventDefault()
    setSaving(true)
    setSuccess(false)
    try {
      const fd = new FormData()
      fd.append('company_name', form.company_name)
      fd.append('primary_color', form.primary_color)
      fd.append('accent_color', form.accent_color)
      fd.append('webhook_url', form.webhook_url)
      fd.append('bonus_success_message', form.bonus_success_message)
      fd.append('bonus_pending_message', form.bonus_pending_message)
      NOTIFY_TOGGLES.forEach(t => fd.append(t.key, String(form[t.key])))
      fd.append('face_verification_enabled', String(form.face_verification_enabled))
      fd.append('face_verification_provider', form.face_verification_provider)
      fd.append('smtp_host', form.smtp_host)
      fd.append('smtp_port', String(form.smtp_port))
      fd.append('smtp_username', form.smtp_username)
      fd.append('smtp_password', form.smtp_password)
      fd.append('smtp_from_email', form.smtp_from_email)
      fd.append('smtp_to_email', form.smtp_to_email)
      fd.append('email_notify_monthly_report', String(form.email_notify_monthly_report))
      fd.append('live_tracking_enabled', String(form.live_tracking_enabled))
      fd.append('live_tracking_interval_minutes', String(form.live_tracking_interval_minutes))
      if (logoFile) fd.append('logo', logoFile)

      await api.patch('/company/config', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      await company.reload()
      setSuccess(true)
      showSuccess('Configuración guardada exitosamente')
      setLogoFile(null)
      setTimeout(() => setSuccess(false), 3000)
      return true
    } catch (err) {
      showError(err.response?.data?.detail || 'Error al guardar la configuración')
      return false
    } finally {
      setSaving(false)
    }
  }

  const handleTestWebhook = async () => {
    setTestStatus('loading')
    setTestMsg('')
    try {
      const res = await api.post('/company/webhook/test')
      setTestStatus('ok')
      setTestMsg(res.data.message || 'Ping enviado correctamente')
    } catch (err) {
      setTestStatus('error')
      setTestMsg(err.response?.data?.detail || 'Error al contactar el Webhook')
    }
    setTimeout(() => setTestStatus(null), 5000)
  }

  const handleSendTestReportEmail = async () => {
    setEmailSending(true)
    setEmailTestStatus(null)
    setEmailTestMsg('')
    // First, save the configuration in case they edited fields
    const saved = await handleSave()
    if (!saved) {
      setEmailSending(false)
      return
    }

    try {
      const res = await api.post('/company/report/send-email')
      setEmailTestStatus('ok')
      setEmailTestMsg(res.data.message || 'Reporte de asistencia mensual enviado exitosamente.')
    } catch (err) {
      setEmailTestStatus('error')
      setEmailTestMsg(err.response?.data?.detail || 'Error al enviar reporte. Verifique la configuración SMTP.')
    } finally {
      setEmailSending(false)
      setTimeout(() => setEmailTestStatus(null), 8000)
    }
  }

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Configuración de Empresa</h2>
        <p className="text-gray-500 text-sm mt-1">Personaliza el nombre y logo que verán todos los empleados</p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Logo section */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Logo de la empresa</h3>

          <div className="flex items-center gap-6">
            {/* Preview */}
            <div className="w-24 h-24 rounded-2xl border-2 border-dashed border-gray-200 flex items-center justify-center bg-gray-50 overflow-hidden flex-shrink-0">
              {(logoPreview || company.logo_url) ? (
                <img
                  src={logoPreview || company.logo_url}
                  alt="Logo"
                  className="w-full h-full object-contain p-2"
                />
              ) : (
                <span className="text-4xl">🏢</span>
              )}
            </div>

            <div className="flex-1">
              <p className="text-sm text-gray-600 mb-3">
                Sube el logo de tu empresa. Se mostrará en el panel admin y en la app móvil.
                <br />
                <span className="text-gray-400">Formatos: PNG, JPG, SVG, WebP. Máx 2MB.</span>
              </p>
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
              >
                📁 Seleccionar imagen
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/svg+xml,image/webp"
                onChange={handleLogoChange}
                className="hidden"
              />
              {logoFile && (
                <p className="text-xs text-green-600 mt-2 font-medium">✅ {logoFile.name} seleccionado</p>
              )}
            </div>
          </div>
        </div>

        {/* Name + Colors */}
        <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
          <h3 className="font-semibold text-gray-900 mb-2">Identidad visual</h3>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Nombre de la empresa
            </label>
            <input
              required
              value={form.company_name}
              onChange={e => setForm({ ...form, company_name: e.target.value })}
              placeholder="Ej: Acme Corporation"
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">Aparece en la barra lateral, login y en la app del empleado</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Color primario
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={form.primary_color}
                  onChange={e => setForm({ ...form, primary_color: e.target.value })}
                  className="w-12 h-10 rounded-lg border border-gray-300 cursor-pointer p-1"
                />
                <input
                  value={form.primary_color}
                  onChange={e => setForm({ ...form, primary_color: e.target.value })}
                  placeholder="#2563eb"
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Color secundario
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={form.accent_color}
                  onChange={e => setForm({ ...form, accent_color: e.target.value })}
                  className="w-12 h-10 rounded-lg border border-gray-300 cursor-pointer p-1"
                />
                <input
                  value={form.accent_color}
                  onChange={e => setForm({ ...form, accent_color: e.target.value })}
                  placeholder="#1d4ed8"
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Messaging & Webhook section */}
        <div className="bg-white rounded-xl shadow-sm p-6 space-y-5">
          <h3 className="font-semibold text-gray-900">Automatización y Mensajes</h3>

          {/* Webhook URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              URL del Webhook (Integraciones)
            </label>
            <div className="flex gap-2">
              <input
                type="url"
                value={form.webhook_url}
                onChange={e => setForm({ ...form, webhook_url: e.target.value })}
                placeholder="https://hook.make.com/... o https://discord.com/api/webhooks/..."
                className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
              <button
                type="button"
                onClick={handleTestWebhook}
                disabled={testStatus === 'loading' || !form.webhook_url}
                className="px-3 py-2 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-lg text-sm font-medium transition disabled:opacity-40 whitespace-nowrap"
              >
                {testStatus === 'loading' ? '⏳ Probando...' : '🔔 Probar'}
              </button>
            </div>
            {testStatus === 'ok' && (
              <p className="text-xs text-green-600 mt-1 font-medium">✅ {testMsg}</p>
            )}
            {testStatus === 'error' && (
              <p className="text-xs text-red-500 mt-1 font-medium">❌ {testMsg}</p>
            )}
            <p className="text-xs text-gray-400 mt-1">Compatible con Make, n8n, Zapier, Discord y cualquier servicio que acepte POST JSON.</p>
          </div>

          {/* Notification toggles */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">Eventos que disparan notificación</label>
            <div className="space-y-2">
              {NOTIFY_TOGGLES.map(toggle => (
                <div
                  key={toggle.key}
                  onClick={() => handleToggle(toggle.key)}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition select-none
                    ${form[toggle.key]
                      ? 'bg-blue-50 border-blue-300 text-blue-800'
                      : 'bg-gray-50 border-gray-200 text-gray-600'
                    }`}
                >
                  {/* Toggle pill */}
                  <div className={`relative flex-shrink-0 w-10 h-5 rounded-full transition-colors ${form[toggle.key] ? 'bg-blue-500' : 'bg-gray-300'}`}>
                    <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${form[toggle.key] ? 'translate-x-5' : 'translate-x-0'}`} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium">{toggle.label}</p>
                    <p className="text-xs text-gray-500">{toggle.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Face verification section */}
          <div className="border-t pt-5 mt-5">
            <h4 className="font-medium text-gray-900 mb-4">🔐 Verificación facial biométrica</h4>

            <div
              onClick={() => handleToggle('face_verification_enabled')}
              className={`flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition select-none mb-4
                ${form.face_verification_enabled
                  ? 'bg-green-50 border-green-300 text-green-800'
                  : 'bg-gray-50 border-gray-200 text-gray-600'
                }`}
            >
              <div className={`relative flex-shrink-0 w-10 h-5 rounded-full transition-colors ${form.face_verification_enabled ? 'bg-green-500' : 'bg-gray-300'}`}>
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.face_verification_enabled ? 'translate-x-5' : 'translate-x-0'}`} />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">Activar verificación facial</p>
                <p className="text-xs text-gray-500">Los empleados deberán verificar su identidad al marcar asistencia</p>
              </div>
            </div>

            {form.face_verification_enabled && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Proveedor de verificación</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, face_verification_provider: 'face_recognition' })}
                    className={`p-4 rounded-lg border-2 text-left transition ${
                      form.face_verification_provider === 'face_recognition'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <p className="text-sm font-medium text-gray-900">🧠 Local (face_recognition)</p>
                    <p className="text-xs text-gray-500 mt-1">Rápido (~100ms), sin costo, requiere cámara 720p+</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, face_verification_provider: 'gemini_vision' })}
                    className={`p-4 rounded-lg border-2 text-left transition ${
                      form.face_verification_provider === 'gemini_vision'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <p className="text-sm font-medium text-gray-900">☁️ Gemini Vision</p>
                    <p className="text-xs text-gray-500 mt-1">Fallback con IA (2-3s), requiere API key</p>
                  </button>
                </div>
              </div>
            )}

            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mt-4">
              <p className="text-xs text-amber-700">
                ⚠️ <strong>Importante:</strong> Cada empleado debe registrar su foto de referencia desde la sección de Empleados → Registrar rostro.
                Sin esto, no podrán marcar asistencia si la verificación facial está activa.
              </p>
            </div>
          </div>

          {/* Bonus messages */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Mensaje de Bono (Objetivo Cumplido)
            </label>
            <input
              required
              value={form.bonus_success_message}
              onChange={e => setForm({ ...form, bonus_success_message: e.target.value })}
              placeholder="Ej: ¡Bonus asegurado!"
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-green-500 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Mensaje de Bono (Progreso / Faltante)
            </label>
            <input
              required
              value={form.bonus_pending_message}
              onChange={e => setForm({ ...form, bonus_pending_message: e.target.value })}
              placeholder="Ej: Faltan {days} días para asegurar tu bono."
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-yellow-500 text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">Usa <code className="bg-gray-100 rounded px-1">{`{days}`}</code> para insertar dinámicamente cuántos días le faltan al empleado.</p>
          </div>
        </div>

        {/* SMTP Configuration Card */}
        <div className="bg-white rounded-xl shadow-sm p-6 space-y-5">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2 text-base">
            📧 Servidor de Correo SMTP y Reportes
          </h3>
          <p className="text-xs text-gray-500 leading-relaxed">
            Configure las credenciales de su propio servidor de correo SMTP para habilitar la distribución automática de reportes de asistencia y bono mensuales.
          </p>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Servidor SMTP (Host)
              </label>
              <input
                value={form.smtp_host}
                onChange={e => setForm({ ...form, smtp_host: e.target.value })}
                placeholder="Ej. smtp.gmail.com o smtp.sendgrid.net"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Puerto SMTP
              </label>
              <input
                type="number"
                value={form.smtp_port}
                onChange={e => setForm({ ...form, smtp_port: parseInt(e.target.value) || 587 })}
                placeholder="587 o 465"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Usuario SMTP (Email)
              </label>
              <input
                value={form.smtp_username}
                onChange={e => setForm({ ...form, smtp_username: e.target.value })}
                placeholder="Ej. reportes@miempresa.com"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Contraseña SMTP
              </label>
              <input
                type="password"
                value={form.smtp_password}
                onChange={e => setForm({ ...form, smtp_password: e.target.value })}
                placeholder="••••••••••••"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Remitente de Correo (De)
              </label>
              <input
                value={form.smtp_from_email}
                onChange={e => setForm({ ...form, smtp_from_email: e.target.value })}
                placeholder="Ej. UruCheck <no-reply@miempresa.com>"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Destinatario de Reportes (Para)
              </label>
              <input
                value={form.smtp_to_email}
                onChange={e => setForm({ ...form, smtp_to_email: e.target.value })}
                placeholder="Ej. admin@miempresa.com"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div
            onClick={() => handleToggle('email_notify_monthly_report')}
            className={`flex items-center gap-3 p-3.5 rounded-lg border cursor-pointer transition select-none
              ${form.email_notify_monthly_report
                ? 'bg-blue-50 border-blue-300 text-blue-800'
                : 'bg-gray-50 border-gray-200 text-gray-600'
              }`}
          >
            <div className={`relative flex-shrink-0 w-10 h-5 rounded-full transition-colors ${form.email_notify_monthly_report ? 'bg-blue-500' : 'bg-gray-300'}`}>
              <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.email_notify_monthly_report ? 'translate-x-5' : 'translate-x-0'}`} />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium">Enviar reporte mensual automáticamente</p>
              <p className="text-xs text-gray-500">Se enviará el primer día de cada mes por correo electrónico a la dirección destinataria</p>
            </div>
          </div>

          {/* Test SMTP Email Trigger */}
          <div className="border-t pt-4 flex items-center justify-between gap-4 flex-wrap">
            <div className="text-xs text-gray-400">
              Pruebe su conexión SMTP enviando un reporte de asistencia ahora mismo.
            </div>
            <button
              type="button"
              onClick={handleSendTestReportEmail}
              disabled={emailSending || !form.smtp_host || !form.smtp_username || !form.smtp_password}
              className="px-4 py-2 bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200 rounded-lg text-xs font-semibold transition disabled:opacity-40 whitespace-nowrap"
            >
              {emailSending ? '⏳ Enviando...' : '✉️ Enviar reporte ahora'}
            </button>
          </div>
          {emailTestStatus === 'ok' && (
            <p className="text-xs text-green-600 font-medium">✅ {emailTestMsg}</p>
          )}
          {emailTestStatus === 'error' && (
            <p className="text-xs text-red-500 font-medium">❌ {emailTestMsg}</p>
          )}
        </div>

        {/* Live preview */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Vista previa</h3>
          <div className="rounded-xl overflow-hidden border border-gray-200">
            {/* Simulated sidebar header */}
            <div
              className="p-4 flex items-center gap-3"
              style={{ backgroundColor: form.accent_color }}
            >
              <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center overflow-hidden">
                {(logoPreview || company.logo_url) ? (
                  <img src={logoPreview || company.logo_url} alt="" className="w-full h-full object-contain p-1" />
                ) : (
                  <span className="text-xl">🏢</span>
                )}
              </div>
              <div>
                <p className="text-white font-bold text-sm">{form.company_name || 'Mi Empresa'}</p>
                <p className="text-white/60 text-xs">Panel Admin</p>
              </div>
            </div>
            {/* Simulated button */}
            <div className="p-4 bg-gray-50">
              <button
                type="button"
                className="px-4 py-2 rounded-lg text-white text-sm font-medium"
                style={{ backgroundColor: form.primary_color }}
              >
                Registrar Entrada
              </button>
              <p className="text-xs text-gray-400 mt-2">Así se verá el botón en la app</p>
            </div>
          </div>
        </div>

        {/* Live GPS Tracking Settings (Hybrid Mode) */}
        <div className="bg-white rounded-xl shadow-sm p-6 space-y-5">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              📍 Geolocalización en Tiempo Real
            </h3>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              App Móvil
            </span>
          </div>
          <p className="text-sm text-gray-500">
            Controla cómo reportan ubicación los empleados durante su jornada de trabajo.
          </p>

          <div
            onClick={() => handleToggle('live_tracking_enabled')}
            className={`flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition select-none
              ${form.live_tracking_enabled
                ? 'bg-blue-50 border-blue-300 text-blue-800'
                : 'bg-gray-50 border-gray-200 text-gray-600'
              }`}
          >
            <div className={`relative flex-shrink-0 w-10 h-5 rounded-full transition-colors ${form.live_tracking_enabled ? 'bg-blue-500' : 'bg-gray-300'}`}>
              <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.live_tracking_enabled ? 'translate-x-5' : 'translate-x-0'}`} />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium">Habilitar reporte de ubicación periódico durante la jornada laboral</p>
              <p className="text-xs text-gray-500">
                Cuando está activo, la app móvil reportará coordenadas automáticamente sólo mientras el empleado tenga la jornada iniciada (entre entrada y salida).
              </p>
            </div>
          </div>

          {form.live_tracking_enabled && (
            <div className="pl-4 border-l-2 border-blue-200 space-y-2">
              <label className="block text-sm font-medium text-gray-700">
                Intervalo de reporte automático (minutos)
              </label>
              <input
                type="number"
                min={5}
                max={120}
                value={form.live_tracking_interval_minutes}
                onChange={e => setForm({ ...form, live_tracking_interval_minutes: parseInt(e.target.value) || 15 })}
                className="w-36 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-400">
                Recomendado: 15 minutos (mínimo 5 min, máximo 120 min).
              </p>
            </div>
          )}

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800 flex items-start gap-2">
            <span className="text-sm">ℹ️</span>
            <div>
              <strong>Solicitud Bajo Demanda:</strong> Aunque este interruptor esté desactivado, los administradores siempre pueden solicitar la ubicación puntual en vivo desde el Dashboard pulsando <strong>"📍 Solicitar Ubicación"</strong>.
            </div>
          </div>
        </div>

        {/* Save */}
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={saving || company.loading}
            className="px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium text-sm hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {saving ? 'Guardando...' : company.loading ? 'Cargando datos...' : 'Guardar cambios'}
          </button>
          {success && (
            <p className="text-green-600 text-sm font-medium">✅ Configuración guardada correctamente</p>
          )}
        </div>
      </form>
    </div>
  )
}

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'

export default function RegisterCompany() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: '',
    slug: '',
    admin_email: '',
    admin_password: '',
    admin_password_confirm: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const generateSlug = (name) => {
    return name.toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
  }

  const handleNameChange = (e) => {
    const name = e.target.value
    setForm(f => ({ ...f, name, slug: generateSlug(name) }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')

    if (form.admin_password !== form.admin_password_confirm) {
      return setError('Las contraseñas no coinciden')
    }
    if (form.admin_password.length < 6) {
      return setError('La contraseña debe tener al menos 6 caracteres')
    }

    setLoading(true)
    try {
      const res = await api.post('/companies/register', {
        name: form.name,
        slug: form.slug,
        admin_email: form.admin_email,
        admin_password: form.admin_password,
        plan_slug: 'free',
      })

      // Save token and redirect
      localStorage.setItem('token', res.data.admin_token)
      localStorage.setItem('user', JSON.stringify({
        id: res.data.admin_id,
        name: res.data.admin_name,
        role: 'admin',
        company_id: res.data.company_id,
        company_name: form.name,
        company_slug: res.data.company_slug,
      }))

      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al registrar la empresa')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-600 to-blue-800">
      <div className="bg-white rounded-2xl shadow-2xl p-10 w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8">
          <span className="text-5xl">🏢</span>
          <h1 className="text-2xl font-bold text-gray-900 mt-4">Registrar Nueva Empresa</h1>
          <p className="text-gray-500 text-sm mt-1">Crea tu cuenta y comienza a gestionar la asistencia</p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          {/* Company name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre de la empresa</label>
            <input
              required value={form.name} onChange={handleNameChange}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ej: Mi Empresa SRL"
            />
          </div>

          {/* Slug */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Identificador único (slug)</label>
            <div className="flex items-center gap-2">
              <span className="text-gray-400 text-sm">app.com/</span>
              <input
                required value={form.slug}
                onChange={e => setForm(f => ({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') }))}
                className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                placeholder="mi-empresa"
                minLength={3}
              />
            </div>
          </div>

          {/* Admin email */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email del administrador</label>
            <input
              type="email" required value={form.admin_email}
              onChange={e => setForm(f => ({ ...f, admin_email: e.target.value }))}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="admin@miempresa.com"
            />
          </div>

          {/* Password */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
              <input
                type="password" required value={form.admin_password}
                onChange={e => setForm(f => ({ ...f, admin_password: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="••••••"
                minLength={6}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirmar</label>
              <input
                type="password" required value={form.admin_password_confirm}
                onChange={e => setForm(f => ({ ...f, admin_password_confirm: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="••••••"
                minLength={6}
              />
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>
          )}

          {/* Plan info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3">
            <p className="text-sm text-blue-800 font-medium">Plan Gratuito</p>
            <p className="text-xs text-blue-600 mt-1">Hasta 10 empleados. Reconocimiento facial incluido.</p>
          </div>

          <button type="submit" disabled={loading}
            className="w-full bg-blue-600 text-white font-semibold rounded-lg px-4 py-2.5 transition disabled:opacity-50 hover:bg-blue-700">
            {loading ? 'Creando empresa...' : 'Crear empresa y comenzar'}
          </button>

          <div className="text-center">
            <button type="button" onClick={() => navigate('/login')}
              className="text-sm text-gray-500 hover:text-gray-700">
              ¿Ya tienes cuenta? Inicia sesión →
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

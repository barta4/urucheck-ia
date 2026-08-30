import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import api from '../api'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [company, setCompany] = useState({ company_name: 'Control de Asistencia', logo_url: null, accent_color: '#1d4ed8' })
  const [showCompanySlug, setShowCompanySlug] = useState(false)
  const [companySlug, setCompanySlug] = useState('')

  useEffect(() => {
    let slug = new URLSearchParams(window.location.search).get('slug')
    if (!slug) {
      try {
        const user = JSON.parse(localStorage.getItem('user'))
        slug = user?.company_slug
      } catch (err) { }
    }
    if (slug) {
      setCompanySlug(slug)
    }
    const url = slug ? `/company/config?slug=${encodeURIComponent(slug)}` : '/company/config'
    api.get(url).then(r => setCompany(r.data)).catch(() => {})
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await login(form.email, form.password, companySlug || null)
      navigate('/dashboard')
    } catch (err) {
      if (err.response?.data?.detail === 'multiple_companies') {
        setShowCompanySlug(true)
        setError('Tu correo está asociado a múltiples empresas. Por favor, ingresa el identificador de tu empresa.')
      } else {
        setError(err.response?.data?.detail || 'Error al iniciar sesión')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: `linear-gradient(135deg, ${company.accent_color}dd, ${company.accent_color})` }}>
      <div className="bg-white rounded-2xl shadow-2xl p-10 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-4 overflow-hidden" style={{ backgroundColor: company.accent_color + '15', border: `2px solid ${company.accent_color}30` }}>
            {company.logo_url ? (
              <img src={company.logo_url} alt="Logo" className="w-full h-full object-contain p-2" />
            ) : (
              <span className="text-4xl">🏢</span>
            )}
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{company.company_name}</h1>
          <p className="text-gray-500 text-sm mt-1">Panel Administrativo</p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="admin@empresa.com" required />
          </div>

          {(showCompanySlug || new URLSearchParams(window.location.search).has('slug')) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Identificador de Empresa (Slug)</label>
              <input type="text" value={companySlug} onChange={e => setCompanySlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                placeholder="mi-empresa" required />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
            <input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••" required />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>
          )}

          <button type="submit" disabled={loading}
            className="w-full text-white font-semibold rounded-lg px-4 py-2.5 transition disabled:opacity-50"
            style={{ backgroundColor: company.accent_color }}>
            {loading ? 'Ingresando...' : 'Ingresar'}
          </button>
        </form>

        <div className="text-center mt-6 pt-6 border-t border-gray-200">
          <p className="text-sm text-gray-500 mb-2">¿No tienes cuenta?</p>
          <a href="/register" className="text-blue-600 font-semibold hover:text-blue-700 text-sm">
            Registrar nueva empresa →
          </a>
        </div>
      </div>
    </div>
  )
}

import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react'
import api from '../api'
import { useAuth } from './AuthContext'

const defaultConfig = {
  company_name: 'Mi Empresa',
  logo_url: null,
  primary_color: '#2563eb',
  accent_color: '#1d4ed8',
  webhook_url: '',
  bonus_success_message: '¡Bonus asegurado!',
  bonus_pending_message: 'Faltan {days} días para asegurar tu bono.',
}

const CompanyContext = createContext({
  ...defaultConfig,
  loading: true,
  reload: () => { },
})

export function CompanyProvider({ children }) {
  const { user } = useAuth()
  const [config, setConfig] = useState(defaultConfig)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      let slug = new URLSearchParams(window.location.search).get('slug')
      if (!slug && user?.company_slug) {
        slug = user.company_slug
      }
      const url = slug ? `/company/config?slug=${encodeURIComponent(slug)}` : '/company/config'
      const res = await api.get(url)
      setConfig(res.data)
      document.documentElement.style.setProperty('--color-primary', res.data.primary_color || '#2563eb')
      document.documentElement.style.setProperty('--color-accent', res.data.accent_color || '#1d4ed8')
      document.title = (res.data.company_name || 'Mi Empresa') + ' — Asistencia'
    } catch (e) {
      console.error('No se pudo cargar configuración de empresa', e)
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => {
    load()
  }, [load])

  const value = useMemo(() => ({ ...config, loading, reload: load }), [config, loading, load])

  return (
    <CompanyContext.Provider value={value}>
      {children}
    </CompanyContext.Provider>
  )
}

export const useCompany = () => useContext(CompanyContext)


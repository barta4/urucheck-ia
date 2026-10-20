import { createContext, useContext, useState, useEffect } from 'react'
import api from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Session restore: the JWT lives in the httpOnly cookie (not readable
    // from JS). We only restore the non-sensitive user profile from
    // localStorage; authorization is enforced server-side on every request.
    const userData = localStorage.getItem('user')
    if (userData) {
      try {
        const parsed = JSON.parse(userData)
        if (parsed.role !== 'admin' && !parsed.is_super_admin) {
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          setUser(null)
        } else {
          setUser(parsed)
        }
      } catch {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        setUser(null)
      }
    }
    setLoading(false)
  }, [])

  const login = async (email, password, companySlug = null) => {
    const payload = { email, password, portal: 'admin' }
    if (companySlug) {
      payload.company_slug = companySlug
    }
    const res = await api.post('/auth/login', payload)
    if (res.data.role !== 'admin' && !res.data.is_super_admin) {
      localStorage.removeItem('user')
      throw new Error('Acceso denegado: Este portal es exclusivo para administradores de empresas. Los empleados deben utilizar la aplicación móvil.')
    }
    // The auth token is set by the backend as an httpOnly cookie — it is
    // deliberately NOT persisted to localStorage (XSS-proof session storage).
    // Legacy 'token' key is cleared in case a pre-migration session exists.
    localStorage.removeItem('token')
    const { access_token, ...userData } = res.data
    localStorage.setItem('user', JSON.stringify(userData))
    setUser(userData)
    return res.data
  }

  const logout = async () => {
    // Server-side revocation + httpOnly cookie clearing (see /auth/logout),
    // not just a local removal.
    try {
      await api.post('/auth/logout')
    } catch (_) {
      // Best-effort: clear locally even if the network call fails
    }
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)

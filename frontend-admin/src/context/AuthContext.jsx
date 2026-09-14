import { createContext, useContext, useState, useEffect } from 'react'
import api from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    const userData = localStorage.getItem('user')
    if (token && userData) {
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
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      throw new Error('Acceso denegado: Este portal es exclusivo para administradores de empresas. Los empleados deben utilizar la aplicación móvil.')
    }
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('user', JSON.stringify(res.data))
    setUser(res.data)
    return res.data
  }

  const logout = () => {
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

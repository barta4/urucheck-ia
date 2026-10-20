import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import * as SecureStore from 'expo-secure-store'
import AsyncStorage from '@react-native-async-storage/async-storage'
import api from '../api'
import { registerForPushNotificationsAsync } from '../services/notifications'
import { getUniqueDeviceId } from '../services/device'
import { clearQueueForUser } from '../offlineQueue'

const AuthContext = createContext(null)

const TOKEN_EXPIRY_MARGIN_MS = 5 * 60 * 1000  // 5 min before expiry

// Decode JWT to extract exp claim
function decodeJWT(token) {
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join(''))
    return JSON.parse(jsonPayload)
  } catch {
    return {}
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tokenExpired, setTokenExpired] = useState(false)

  // Restore session on mount
  useEffect(() => {
    const restore = async () => {
      try {
        const token = await SecureStore.getItemAsync('token')
        const userData = await SecureStore.getItemAsync('user')
        if (token && userData) {
          const parsed = JSON.parse(userData)
          setUser(parsed)

          // Check JWT exp claim
          const decoded = decodeJWT(token)
          const exp = decoded.exp ? decoded.exp * 1000 : null
          if (exp && Date.now() > exp - TOKEN_EXPIRY_MARGIN_MS) {
            setTokenExpired(true)
          }
        }
      } catch (e) {
        console.log('[Auth] Restore error:', e)
      }
      setLoading(false)
    }
    restore()
  }, [])

  const login = async (email, password, companySlug = null) => {
    const deviceId = await getUniqueDeviceId()
    const payload = { email, password, device_id: deviceId }
    // Multi-tenant support: emails can exist in several companies; the
    // backend answers 400 "multiple_companies" when the slug is needed.
    if (companySlug) payload.company_slug = companySlug.trim().toLowerCase()
    const res = await api.post('/auth/login', payload)
    await SecureStore.setItemAsync('token', res.data.access_token)
    await SecureStore.setItemAsync('user', JSON.stringify(res.data))
    setUser(res.data)
    setTokenExpired(false)

    try {
      const pushToken = await registerForPushNotificationsAsync()
      if (pushToken) {
        await api.put('/notifications/push-token', { token: pushToken })
        console.log('[Auth] Push token registered to server')
      }
    } catch (e) {
      console.log('[Auth] Push token registration error:', e)
    }
  }

  const logout = async () => {
    try {
      // Best-effort server-side revocation (token may already be invalid)
      try { await api.post('/auth/logout') } catch {}
      // SECURITY: wipe this user's offline queue (+photos) BEFORE destroying
      // the session — pending marks must never sync under the next account
      // on a shared device.
      const loggingOutUserId = user?.user_id
      if (loggingOutUserId) {
        await clearQueueForUser(loggingOutUserId)
      }
      await SecureStore.deleteItemAsync('token')
      await SecureStore.deleteItemAsync('user')
      await AsyncStorage.removeItem('company_config_cache')
    } catch {}
    setUser(null)
    setTokenExpired(false)
  }

  const reauthenticate = useCallback(async (email, password) => {
    try {
      await login(email, password)
      return true
    } catch {
      return false
    }
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, tokenExpired, reauthenticate }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)

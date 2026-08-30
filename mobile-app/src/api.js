import axios from 'axios'
import * as SecureStore from 'expo-secure-store'
import Constants from 'expo-constants'
import { DeviceEventEmitter } from 'react-native'

import AsyncStorage from '@react-native-async-storage/async-storage'

export const DEFAULT_API_URL = Constants.expoConfig?.extra?.API_URL || 'https://asistencia.urufile.com/api'

const api = axios.create({ baseURL: DEFAULT_API_URL, timeout: 30000 })

api.interceptors.request.use(async config => {
  try {
    const customUrl = await AsyncStorage.getItem('custom_api_url')
    if (customUrl) {
      config.baseURL = customUrl
      api.defaults.baseURL = customUrl // Keep default synchronized
    }
  } catch (e) {}

  const token = await SecureStore.getItemAsync('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 401 interceptor → emit RN event so app can prompt re-login
api.interceptors.response.use(
  res => res,
  async err => {
    if (err.response?.status === 401) {
      try {
        await SecureStore.deleteItemAsync('token')
        await SecureStore.deleteItemAsync('user')
      } catch {}
      DeviceEventEmitter.emit('auth:tokenExpired', {})
    }
    return Promise.reject(err)
  }
)

export default api

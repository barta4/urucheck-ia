import { useState, useEffect, useCallback } from 'react'
import AsyncStorage from '@react-native-async-storage/async-storage'
import api from '../api'
import { useAuth } from '../context/AuthContext'

const DEFAULT = {
  company_name: 'UruCheck IA',
  logo_url: null,
  primary_color: '#2563eb',
  accent_color: '#1d4ed8',
}

const STORAGE_KEY = 'company_config_cache'

export function useCompany() {
  const { user } = useAuth()
  const [company, setCompany] = useState(DEFAULT)

  const fetchConfig = useCallback(async () => {
    try {
      // 1. Try to load cached config first from local storage for offline support
      const cachedStr = await AsyncStorage.getItem(STORAGE_KEY)
      if (cachedStr) {
        try {
          const parsed = JSON.parse(cachedStr)
          setCompany(parsed)
        } catch {}
      }

      // 2. Query endpoint from server (with current auth token in header)
      const res = await api.get('/company/config')
      let data = res.data
      if (data.logo_url && !data.logo_url.startsWith('http')) {
        const base = (api.defaults.baseURL || '').replace(/\/api$/, '')
        data.logo_url = base + data.logo_url
      }
      setCompany(data)
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch (e) {
      // If offline, keep loaded cached config or fallback
    }
  }, [user])

  useEffect(() => {
    if (!user) {
      AsyncStorage.getItem(STORAGE_KEY).then(cachedStr => {
        if (cachedStr) {
          try {
            setCompany(JSON.parse(cachedStr))
          } catch {
            setCompany(DEFAULT)
          }
        } else {
          setCompany(DEFAULT)
        }
      })
    } else {
      fetchConfig()
    }
  }, [user, fetchConfig])

  return company
}


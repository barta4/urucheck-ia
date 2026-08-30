import axios from 'axios'

// URL injected at container runtime via /docker-entrypoint.d/inject-env.sh
// Falls back to relative /api for local dev (vite proxy handles it)
const API_URL = window.__ENV__?.VITE_API_URL || import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_URL
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

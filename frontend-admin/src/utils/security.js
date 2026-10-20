import api from '../api'

const HEX_COLOR_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/

/**
 * Validate a color coming from an API/DB before interpolating it into inline
 * styles. Prevents CSS injection from admin-configurable branding fields.
 * Returns the value if it is a plain hex color, otherwise the fallback.
 */
export function safeColor(value, fallback = '#1d4ed8') {
  return typeof value === 'string' && HEX_COLOR_RE.test(value.trim()) ? value.trim() : fallback
}

/**
 * Validate an external link before rendering it as <a href>. Only http(s)
 * URLs pass — blocks javascript:/data: schemes in admin-configurable URLs.
 */
export function safeExternalUrl(value) {
  if (typeof value !== 'string' || !value.trim()) return null
  try {
    const url = new URL(value.trim())
    if (url.protocol === 'http:' || url.protocol === 'https:') return url.toString()
  } catch (_) { /* invalid URL */ }
  return null
}

/**
 * Fetch a protected API resource (e.g. attendance photos) using the
 * Authorization header and return a browser object URL.
 * Keeps JWTs out of <img src> query strings (which leak into access logs,
 * proxies and browser history).
 */
export async function fetchProtectedBlobUrl(path) {
  const res = await api.get(path, { responseType: 'blob' })
  return URL.createObjectURL(res.data)
}

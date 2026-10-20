/**
 * Offline queue for attendance marks.
 *
 * SECURITY & CORRECTNESS DESIGN (v2):
 *  - Queue items live in expo-secure-store (encrypted at rest by the OS
 *    keychain/keystore). Only the ordered list of item IDs stays in
 *    AsyncStorage (non-sensitive). Legacy plaintext queues are migrated
 *    transparently on first read.
 *  - Every item records the user_id that created it: pending marks are NEVER
 *    synced under a different session (shared devices).
 *  - A module-level mutex prevents concurrent syncQueue() runs (NetInfo can
 *    fire several connectivity events in a row → duplicate uploads → phantom
 *    check_in + break_start pairs on the server).
 *  - A mark is considered REGISTERED only if the server response contains
 *    `log_id`. Rejections arrive as HTTP 200 with status:"warning" and NO
 *    log_id (out of geofence, weak GPS, face verification required, day
 *    already complete). Those items are marked FAILED with the server
 *    message and the selfie is KEPT, instead of being silently discarded.
 *  - Photos of synced / aged-out / deleted items are always removed from disk.
 */
import AsyncStorage from '@react-native-async-storage/async-storage'
import * as FileSystem from 'expo-file-system/legacy'
import * as SecureStore from 'expo-secure-store'
import api from './api'

const LEGACY_QUEUE_KEY = '@attendance_offline_queue'
const INDEX_KEY = '@attendance_offline_queue_index'
const MAX_QUEUE_AGE_HOURS = 48

const itemKey = (id) => `@queue_item_${id}`

let _syncInFlight = false

/**
 * Current authenticated user id (from the secure-stored session).
 */
export async function getCurrentUserId() {
  try {
    const raw = await SecureStore.getItemAsync('user')
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed?.user_id || null
  } catch {
    return null
  }
}

/**
 * One-time migration from the old plaintext AsyncStorage queue.
 * Legacy items are stamped with the CURRENT user (single-device assumption)
 * so they keep syncing for the person who most likely created them.
 */
let _migrated = false
async function migrateLegacyQueue() {
  if (_migrated) return
  _migrated = true
  try {
    const raw = await AsyncStorage.getItem(LEGACY_QUEUE_KEY)
    if (!raw) return
    const items = JSON.parse(raw)
    if (!Array.isArray(items) || items.length === 0) {
      await AsyncStorage.removeItem(LEGACY_QUEUE_KEY)
      return
    }
    const currentUserId = await getCurrentUserId()
    const queue = items.map(it => ({ ...it, user_id: it.user_id || currentUserId }))
    await persistQueue(queue)
    await AsyncStorage.removeItem(LEGACY_QUEUE_KEY)
  } catch {
    // Non-fatal: worst case the legacy queue ages out
  }
}

/**
 * Write the whole queue: index (IDs, ordered) in AsyncStorage, items in SecureStore.
 * Deletes SecureStore entries for IDs no longer present.
 */
async function persistQueue(items) {
  const ids = items.map(i => i.id)
  const prevIdsRaw = await AsyncStorage.getItem(INDEX_KEY)
  const prevIds = prevIdsRaw ? JSON.parse(prevIdsRaw) : []

  for (const id of prevIds) {
    if (!ids.includes(id)) {
      try { await SecureStore.deleteItemAsync(itemKey(id)) } catch {}
    }
  }
  for (const item of items) {
    // SecureStore values are limited to ~2048 bytes on Android keychain.
    // Items are small (~300 B: coords, timestamps, photo PATH) so this is safe.
    await SecureStore.setItemAsync(itemKey(item.id), JSON.stringify(item))
  }
  await AsyncStorage.setItem(INDEX_KEY, JSON.stringify(ids))
}

/**
 * Get all pending queue items (every user — UI screens filter as needed).
 */
export async function getQueue() {
  await migrateLegacyQueue()
  try {
    const idsRaw = await AsyncStorage.getItem(INDEX_KEY)
    const ids = idsRaw ? JSON.parse(idsRaw) : []
    const items = []
    for (const id of ids) {
      const raw = await SecureStore.getItemAsync(itemKey(id))
      if (!raw) continue
      try {
        items.push(JSON.parse(raw))
      } catch {
        try { await SecureStore.deleteItemAsync(itemKey(id)) } catch {}
      }
    }
    return items
  } catch {
    return []
  }
}

/**
 * Add a mark to the offline queue.
 * @param {Object} markData - { latitude, longitude, gps_accuracy, device_timestamp, photoUri, user_id }
 */
export async function addToQueue(markData) {
  const queue = await getQueue()
  const item = {
    ...markData,
    queued_at: new Date().toISOString(),
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
    status: 'pending',
  }
  queue.push(item)
  await persistQueue(queue)
  return item
}

/**
 * Remove an item (and its photo) from the queue.
 */
export async function removeFromQueue(itemId, deletePhoto = true) {
  const queue = await getQueue()
  const item = queue.find(i => i.id === itemId)
  const filtered = queue.filter(i => i.id !== itemId)
  await persistQueue(filtered)
  if (item && deletePhoto && item.photoUri) {
    await deleteQueuedPhoto(item.photoUri)
  }
}

/**
 * Mark an item as failed, storing the reason (e.g. the server rejection message).
 */
export async function markItemFailed(itemId, errorMsg = 'Sincronización fallida') {
  const queue = await getQueue()
  const item = queue.find(i => i.id === itemId)
  if (item) {
    item.status = 'failed'
    item.error = errorMsg
    await persistQueue(queue)
  }
}

/**
 * Clean up old queue items (older than MAX_QUEUE_AGE_HOURS).
 * Photos of removed items are deleted so they never orphan on disk.
 */
export async function cleanOldQueue() {
  const queue = await getQueue()
  const cutoff = new Date(Date.now() - MAX_QUEUE_AGE_HOURS * 60 * 60 * 1000)
  const kept = queue.filter(item => new Date(item.queued_at) > cutoff)
  const removed = queue.filter(item => new Date(item.queued_at) <= cutoff)
  if (removed.length > 0) {
    for (const item of removed) {
      if (item.photoUri) await deleteQueuedPhoto(item.photoUri)
    }
    await persistQueue(kept)
  }
}

/**
 * Delete every pending/failed item of a given user (logout hygiene).
 * Called with the user id BEFORE the session is destroyed.
 */
export async function clearQueueForUser(userId) {
  if (!userId) return 0
  const queue = await getQueue()
  const own = queue.filter(i => i.user_id === userId)
  if (own.length === 0) return 0
  for (const item of own) {
    if (item.photoUri) await deleteQueuedPhoto(item.photoUri)
  }
  await persistQueue(queue.filter(i => i.user_id !== userId))
  return own.length
}

/**
 * Get queue count for the CURRENT user (for UI badge).
 */
export async function getQueueCount() {
  const currentUserId = await getCurrentUserId()
  const queue = await getQueue()
  return queue.filter(item => item.status === 'pending' && (!item.user_id || item.user_id === currentUserId)).length
}

/**
 * Interpret the server response for a queued mark.
 * HTTP 2xx does NOT mean the mark was registered: validation rejections
 * (out of geofence, weak GPS, face verification required, day complete)
 * also return 200 with status:"warning" — but WITHOUT log_id.
 * Returns { ok, feedback }.
 */
function _interpretMarkResponse(body) {
  let data = null
  try {
    data = typeof body === 'string' ? JSON.parse(body) : body
  } catch {
    data = null
  }
  if (!data || typeof data !== 'object') {
    return { ok: false, feedback: null }
  }
  if (data.log_id) {
    return { ok: true, feedback: data }
  }
  // Rejection with a friendly message from the server.
  // Handles both AttendanceResponse warnings (title+message) and raw
  // FastAPI errors (detail string, e.g. validation / 5xx payloads).
  let reason
  if (data.title) {
    reason = `${data.title}: ${data.message || 'sin detalle'}`
  } else if (typeof data.detail === 'string') {
    reason = data.detail
  } else {
    reason = 'Marcación rechazada por el servidor'
  }
  return { ok: false, feedback: data, reason: reason.slice(0, 300) }
}

/**
 * Sync all pending queue items of the CURRENT user.
 * Concurrency-safe (mutex): parallel callers get { skipped: true }.
 * @returns {Object} { synced, failed, skipped? }
 */
export async function syncQueue(onProgress) {
  if (_syncInFlight) {
    return { synced: 0, failed: 0, skipped: true }
  }
  _syncInFlight = true
  try {
    await cleanOldQueue()
    const currentUserId = await getCurrentUserId()
    const queue = await getQueue()
    const pendingAll = queue.filter(x => x.status === 'pending')
    const mine = pendingAll.filter(x => !x.user_id || x.user_id === currentUserId)
    let synced = 0
    let failed = 0
    let progress = 0

    for (const item of mine) {
      progress++
      if (onProgress) onProgress(progress, mine.length)

      try {
        const token = await SecureStore.getItemAsync('token')
        if (!token) {
          // Session gone mid-sync: stop, leave items pending
          break
        }

        const url = `${api.defaults.baseURL}/attendance/mark`

        if (item.photoUri) {
          const result = await FileSystem.uploadAsync(url, item.photoUri, {
            httpMethod: 'POST',
            uploadType: 1,
            fieldName: 'photo',
            headers: { Authorization: `Bearer ${token}` },
            parameters: {
              latitude: item.latitude?.toString() || '',
              longitude: item.longitude?.toString() || '',
              gps_accuracy: item.gps_accuracy?.toString() || '0',
              device_timestamp: item.device_timestamp || new Date(item.queued_at).toISOString(),
            },
          })

          if (result.status >= 200 && result.status < 300) {
            const { ok, reason } = _interpretMarkResponse(result.body)
            if (ok) {
              await removeFromQueue(item.id)
              synced++
            } else {
              // Server REJECTED the mark (200 + warning): keep item + photo
              await markItemFailed(item.id, reason || 'Marcación rechazada por el servidor')
              failed++
            }
          } else {
            const { reason } = _interpretMarkResponse(result.body)
            await markItemFailed(item.id, reason || `Servidor respondió ${result.status}`)
            failed++
          }
        } else {
          const formData = new FormData()
          if (item.latitude) formData.append('latitude', item.latitude.toString())
          if (item.longitude) formData.append('longitude', item.longitude.toString())
          formData.append('gps_accuracy', (item.gps_accuracy || 0).toString())
          formData.append('device_timestamp', item.device_timestamp || new Date(item.queued_at).toISOString())

          try {
            const res = await api.post('/attendance/mark', formData)
            const { ok, reason } = _interpretMarkResponse(res.data)
            if (ok) {
              await removeFromQueue(item.id)
              synced++
            } else {
              await markItemFailed(item.id, reason || 'Marcación rechazada por el servidor')
              failed++
            }
          } catch (err) {
            // Network-level failure: keep item PENDING for a later retry
            if (err.response) {
              const { reason } = _interpretMarkResponse(err.response.data)
              await markItemFailed(item.id, reason || `Servidor respondió ${err.response.status}`)
              failed++
            } else {
              failed++
            }
          }
        }
      } catch (err) {
        // Unexpected error (e.g. photo file missing): mark failed, keep data
        await markItemFailed(item.id, `Error inesperado: ${err?.message || err}`)
        failed++
      }
    }

    return { synced, failed }
  } finally {
    _syncInFlight = false
  }
}

/**
 * Delete local photo from queue (after sync or item removal).
 */
export async function deleteQueuedPhoto(uri) {
  try {
    const info = await FileSystem.getInfoAsync(uri)
    if (info.exists) {
      await FileSystem.deleteAsync(uri)
    }
  } catch {
    // ignore
  }
}
